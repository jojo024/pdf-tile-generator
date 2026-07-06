"""Reusable dialogs: errors, success, and About (with manual update check)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdf_tile_generator import APP_NAME, __version__
from pdf_tile_generator.gui.workers import UpdateCheckWorker
from pdf_tile_generator.pdf.generator import GenerationResult
from pdf_tile_generator.update import ReleaseInfo


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
    """About box with version info and a manual "Check for Updates" button.

    The update check is the application's only network access and never runs
    without this explicit click. When a newer release exists, the user gets a
    button that opens the release page in the browser - nothing is downloaded
    or installed automatically.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(420)
        self._worker: UpdateCheckWorker | None = None
        self._release: ReleaseInfo | None = None

        body = QLabel(
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Create printable PDF contact sheets: image tiles with captions "
            "generated from filenames.</p>"
            "<p>Offline by default — no telemetry, no automatic updates. The only "
            "network access is the update check below, and only when you click it.</p>"
            "<p>Built with PySide6, ReportLab, and Pillow.</p>"
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.check_button = QPushButton("Check for Updates")
        self.check_button.setToolTip(
            "Contact github.com once to see whether a newer version exists"
        )
        self.check_button.clicked.connect(self._start_check)
        self.download_button = QPushButton("Open Download Page")
        self.download_button.setVisible(False)
        self.download_button.clicked.connect(self._open_download_page)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)

        update_row = QHBoxLayout()
        update_row.addWidget(self.check_button)
        update_row.addWidget(self.download_button)
        update_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(body)
        layout.addLayout(update_row)
        layout.addWidget(self.status_label)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

    def _start_check(self) -> None:
        if self._worker is not None:
            return
        self.check_button.setEnabled(False)
        self.download_button.setVisible(False)
        self.status_label.setText("Checking for updates…")
        self._worker = UpdateCheckWorker()
        self._worker.updateAvailable.connect(self._on_update_available)
        self._worker.upToDate.connect(self._on_up_to_date)
        self._worker.checkFailed.connect(self._on_check_failed)
        self._worker.finished.connect(self._on_check_finished)
        self._worker.start()

    def _on_update_available(self, release: ReleaseInfo) -> None:
        self._release = release
        self.status_label.setText(
            f"Version {release.version} is available (you have {__version__})."
        )
        self.download_button.setVisible(True)

    def _on_up_to_date(self) -> None:
        self.status_label.setText(f"You are up to date ({__version__}).")

    def _on_check_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_check_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self.check_button.setEnabled(True)

    def _open_download_page(self) -> None:
        if self._release is not None:
            QDesktopServices.openUrl(QUrl(self._release.url))

    def closeEvent(self, event) -> None:  # noqa: ANN001 - Qt override
        if self._worker is not None:
            self._worker.wait(3000)
        super().closeEvent(event)


def show_about(parent: QWidget | None) -> None:
    """Show the About dialog."""
    AboutDialog(parent).exec()
