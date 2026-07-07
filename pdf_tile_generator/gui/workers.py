"""Background workers: lazy thumbnail loading and PDF generation.

Both workers keep the UI thread free. Thumbnails run on the global
``QThreadPool``; PDF generation runs on a dedicated ``QThread`` and is
cancellable through a ``threading.Event`` shared with the generator.
"""

from __future__ import annotations

import logging
import threading

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThread, Signal, Slot
from PySide6.QtGui import QImage

from pdf_tile_generator.images.loader import ImageLoadError
from pdf_tile_generator.images.thumbnail import make_thumbnail
from pdf_tile_generator.models.settings import ProjectSettings
from pdf_tile_generator.pdf.generator import (
    GenerationResult,
    PDFGenerationCancelled,
    PDFGenerationError,
    PDFGenerator,
    TileJob,
)
from pdf_tile_generator.update import (
    PendingUpdate,
    UpdateCheckError,
    VelopackError,
    VelopackUpdater,
    check_for_update,
)

logger = logging.getLogger(__name__)


def pil_to_qimage(image: Image.Image) -> QImage:
    """Convert a Pillow image to a QImage (always RGBA to keep it simple)."""
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return qimage.copy()  # detach from the Python buffer before it is freed


class ThumbnailSignals(QObject):
    """Signals for :class:`ThumbnailTask` (QRunnable cannot define signals)."""

    ready = Signal(str, QImage)  # path, thumbnail
    failed = Signal(str, str)  # path, error message


class ThumbnailTask(QRunnable):
    """Load one thumbnail on the thread pool."""

    def __init__(self, path: str, signals: ThumbnailSignals) -> None:
        super().__init__()
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            with make_thumbnail(self._path) as thumbnail:
                self._signals.ready.emit(self._path, pil_to_qimage(thumbnail))
        except ImageLoadError as exc:
            self._signals.failed.emit(self._path, str(exc))
        except Exception:  # noqa: BLE001 - a bad file must never kill the pool
            logger.exception("Unexpected error creating thumbnail for %s", self._path)
            self._signals.failed.emit(self._path, "Could not create thumbnail")


class PdfWorker(QThread):
    """Runs :class:`PDFGenerator` off the UI thread."""

    progressChanged = Signal(int, int)  # done, total
    succeeded = Signal(object)  # GenerationResult
    failed = Signal(str)  # user-friendly error message
    cancelled = Signal()

    def __init__(self, settings: ProjectSettings, jobs: list[TileJob]) -> None:
        super().__init__()
        self._settings = settings
        self._jobs = jobs
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation; the generator checks this between images."""
        self._cancel_event.set()

    def run(self) -> None:
        generator = PDFGenerator(self._settings)
        try:
            result: GenerationResult = generator.generate(
                self._jobs,
                progress=lambda done, total: self.progressChanged.emit(done, total),
                cancel_event=self._cancel_event,
            )
        except PDFGenerationCancelled:
            self.cancelled.emit()
        except PDFGenerationError as exc:
            self.failed.emit(str(exc))
        except Exception:  # noqa: BLE001 - never let the app crash
            logger.exception("Unexpected PDF generation failure")
            self.failed.emit("An unexpected error occurred while generating the PDF.")
        else:
            self.succeeded.emit(result)


class UpdateCheckWorker(QThread):
    """Runs the manual update check off the UI thread.

    The network request happens only when the user clicks "Check for
    Updates"; this thread exists purely so a slow connection cannot freeze
    the About dialog.
    """

    updateAvailable = Signal(object)  # ReleaseInfo
    upToDate = Signal()
    checkFailed = Signal(str)  # user-friendly message

    def run(self) -> None:
        try:
            release = check_for_update()
        except UpdateCheckError as exc:
            self.checkFailed.emit(str(exc))
        except Exception:  # noqa: BLE001 - never let the app crash
            logger.exception("Unexpected update check failure")
            self.checkFailed.emit("Could not check for updates.")
        else:
            if release is None:
                self.upToDate.emit()
            else:
                self.updateAvailable.emit(release)


class VelopackCheckWorker(QThread):
    """Checks for a Velopack update off the UI thread."""

    updateAvailable = Signal(object)  # PendingUpdate
    upToDate = Signal()
    checkFailed = Signal(str)

    def __init__(self, updater: VelopackUpdater) -> None:
        super().__init__()
        self._updater = updater

    def run(self) -> None:
        try:
            update = self._updater.check()
        except VelopackError as exc:
            self.checkFailed.emit(str(exc))
        except Exception:  # noqa: BLE001 - never let the app crash
            logger.exception("Unexpected Velopack check failure")
            self.checkFailed.emit("Could not check for updates.")
        else:
            if update is None:
                self.upToDate.emit()
            else:
                self.updateAvailable.emit(update)


class VelopackDownloadWorker(QThread):
    """Downloads a Velopack update off the UI thread, reporting progress."""

    progressChanged = Signal(int)  # 0-100
    downloaded = Signal(object)  # PendingUpdate
    downloadFailed = Signal(str)

    def __init__(self, updater: VelopackUpdater, update: PendingUpdate) -> None:
        super().__init__()
        self._updater = updater
        self._update = update

    def run(self) -> None:
        try:
            self._updater.download(
                self._update, progress=lambda pct: self.progressChanged.emit(int(pct))
            )
        except VelopackError as exc:
            self.downloadFailed.emit(str(exc))
        except Exception:  # noqa: BLE001 - never let the app crash
            logger.exception("Unexpected Velopack download failure")
            self.downloadFailed.emit("The update could not be downloaded.")
        else:
            self.downloaded.emit(self._update)
