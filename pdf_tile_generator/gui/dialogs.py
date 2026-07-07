"""Reusable dialogs: errors, success, and About (with manual update check)."""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdf_tile_generator import APP_NAME, __version__
from pdf_tile_generator.gui.workers import (
    UpdateCheckWorker,
    VelopackCheckWorker,
    VelopackDownloadWorker,
)
from pdf_tile_generator.pdf.generator import GenerationResult
from pdf_tile_generator.update import PendingUpdate, ReleaseInfo, VelopackUpdater


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    """Show a user-friendly error dialog."""
    QMessageBox.critical(parent, title, message)


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    """Show a non-fatal warning dialog."""
    QMessageBox.warning(parent, title, message)


def confirm_overwrite(parent: QWidget | None, path: str) -> bool:
    """Ask before overwriting an existing file. Returns True to proceed."""
    answer = QMessageBox.question(
        parent,
        "Overwrite file?",
        f"The file already exists:\n\n{path}\n\nDo you want to replace it?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def show_generation_success(parent: QWidget | None, result: GenerationResult) -> None:
    """Report a successful run, including any skipped images."""
    message = (
        f"PDF created successfully:\n{result.output_path}\n\n"
        f"{result.image_count} images on {result.page_count} "
        f"page{'s' if result.page_count != 1 else ''}."
    )
    if result.skipped:
        names = "\n".join(f"  • {path}: {reason}" for path, reason in result.skipped[:10])
        more = len(result.skipped) - 10
        if more > 0:
            names += f"\n  … and {more} more"
        message += f"\n\n{len(result.skipped)} image(s) could not be read:\n{names}"
        QMessageBox.warning(parent, "PDF created (with warnings)", message)
    else:
        QMessageBox.information(parent, "PDF created", message)


class AboutDialog(QDialog):
    """About box with version info and a "Check for Updates" button.

    Two update paths, chosen automatically:

    * **Installed build (Velopack):** checking, downloading (delta when
      possible), and installing all happen in-app; the user never re-downloads
      the whole program. A progress bar shows the download, then a restart
      applies it.
    * **Source or portable build:** falls back to the manual flow - checking
      the GitHub API and opening the release page in the browser.

    Either way the network is only touched when the user clicks the button.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(440)
        self._updater = VelopackUpdater()
        self._can_self_update = self._updater.is_available()
        self._worker: QDialog | None = None  # active QThread (typed loosely)
        self._release: ReleaseInfo | None = None  # manual-flow result
        self._pending: PendingUpdate | None = None  # velopack-flow result
        self._downloaded = False

        update_note = (
            "This installed copy can update itself: it downloads only what "
            "changed and installs on restart."
            if self._can_self_update
            else "Offline by default — no telemetry, no automatic updates. The only "
            "network access is the update check below, and only when you click it."
        )
        body = QLabel(
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Create printable PDF contact sheets: image tiles with captions "
            "generated from filenames.</p>"
            f"<p>{update_note}</p>"
            "<p>Built with PySide6, ReportLab, and Pillow.</p>"
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.check_button = QPushButton("Check for Updates")
        self.check_button.clicked.connect(self._start_check)
        self.action_button = QPushButton()  # "Download & Install" or "Open Download Page"
        self.action_button.setVisible(False)
        self.action_button.clicked.connect(self._on_action)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)

        update_row = QHBoxLayout()
        update_row.addWidget(self.check_button)
        update_row.addWidget(self.action_button)
        update_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(body)
        layout.addLayout(update_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

    # --------------------------------------------------------------- checking

    def _start_check(self) -> None:
        if self._worker is not None:
            return
        self.check_button.setEnabled(False)
        self.action_button.setVisible(False)
        self.progress.setVisible(False)
        self.status_label.setText("Checking for updates…")
        if self._can_self_update:
            worker = VelopackCheckWorker(self._updater)
            worker.updateAvailable.connect(self._on_velopack_update_available)
        else:
            worker = UpdateCheckWorker()
            worker.updateAvailable.connect(self._on_manual_update_available)
        worker.upToDate.connect(self._on_up_to_date)
        worker.checkFailed.connect(self._on_check_failed)
        worker.finished.connect(self._on_check_finished)
        self._worker = worker
        worker.start()

    def _on_manual_update_available(self, release: ReleaseInfo) -> None:
        self._release = release
        self.status_label.setText(
            f"Version {release.version} is available (you have {__version__})."
        )
        self.action_button.setText("Open Download Page")
        self.action_button.setVisible(True)

    def _on_velopack_update_available(self, update: PendingUpdate) -> None:
        self._pending = update
        self.status_label.setText(
            f"Version {update.version} is available (you have {__version__})."
        )
        self.action_button.setText("Download && Install")
        self.action_button.setVisible(True)

    def _on_up_to_date(self) -> None:
        self.status_label.setText(f"You are up to date ({__version__}).")

    def _on_check_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_check_finished(self) -> None:
        self._clear_worker()
        self.check_button.setEnabled(True)

    # ------------------------------------------------------------ downloading

    def _on_action(self) -> None:
        if self._can_self_update and self._pending is not None:
            if self._downloaded:
                self._apply_update()
            else:
                self._start_download()
        elif self._release is not None:
            QDesktopServices.openUrl(QUrl(self._release.url))

    def _start_download(self) -> None:
        if self._worker is not None or self._pending is None:
            return
        self.action_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText("Downloading update…")
        worker = VelopackDownloadWorker(self._updater, self._pending)
        worker.progressChanged.connect(self.progress.setValue)
        worker.downloaded.connect(self._on_downloaded)
        worker.downloadFailed.connect(self._on_download_failed)
        worker.finished.connect(self._clear_worker)
        self._worker = worker
        worker.start()

    def _on_downloaded(self, _update: PendingUpdate) -> None:
        self._downloaded = True
        self.progress.setValue(100)
        self.status_label.setText(
            "Update downloaded. Click “Restart & Install” to finish — the app "
            "will close and reopen on the new version."
        )
        self.action_button.setText("Restart && Install")
        self.action_button.setEnabled(True)
        self.check_button.setEnabled(True)

    def _on_download_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.status_label.setText(message)
        self.action_button.setEnabled(True)
        self.check_button.setEnabled(True)

    def _apply_update(self) -> None:
        if self._pending is None:
            return
        self.status_label.setText("Restarting to install the update…")
        try:
            self._updater.apply_and_restart(self._pending)  # does not return
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(str(exc))

    # -------------------------------------------------------------- lifecycle

    def _clear_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def closeEvent(self, event) -> None:  # noqa: ANN001 - Qt override
        worker = self._worker
        if worker is not None:
            # Detach signals first so a download that finishes after the dialog
            # is gone cannot call back into a destroyed widget, then wait for
            # the thread to actually stop before returning.
            with contextlib.suppress(RuntimeError, TypeError):
                worker.disconnect()
            self._worker = None
            worker.wait(15000)
            worker.deleteLater()
        super().closeEvent(event)


def show_about(parent: QWidget | None) -> None:
    """Show the About dialog."""
    AboutDialog(parent).exec()
