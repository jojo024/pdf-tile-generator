"""Main application window."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from pdf_tile_generator import APP_NAME, ORG_NAME
from pdf_tile_generator.gui import dialogs
from pdf_tile_generator.gui.image_list import ImageListWidget
from pdf_tile_generator.gui.preview import PreviewPanel
from pdf_tile_generator.gui.settings_panel import SettingsPanel
from pdf_tile_generator.gui.workers import PdfWorker
from pdf_tile_generator.models.settings import ProjectSettings
from pdf_tile_generator.pdf.generator import GenerationResult, TileJob

logger = logging.getLogger(__name__)

_FILE_DIALOG_FILTER = (
    "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp);;All files (*.*)"
)


class MainWindow(QMainWindow):
    """Assembles the image list, settings, preview, and generation flow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 720)
        self._worker: PdfWorker | None = None
        self._qsettings = QSettings(ORG_NAME, APP_NAME)

        self.image_list = ImageListWidget(self)
        self.settings_panel = SettingsPanel(self)
        self.preview_panel = PreviewPanel(self)

        self.generate_button = QPushButton("Generate PDF")
        self.generate_button.setToolTip("Create the PDF contact sheet (Ctrl+G)")
        self.generate_button.setShortcut(QKeySequence("Ctrl+G"))
        self.generate_button.setDefault(True)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)

        self._build_layout()
        self._build_menu()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Add images to begin")

        self.image_list.add_button.clicked.connect(self._add_images_dialog)
        self.image_list.listChanged.connect(self._refresh_preview)
        self.settings_panel.settingsChanged.connect(self._refresh_preview)
        self.settings_panel.titleCaseChanged.connect(self.image_list.set_title_case)
        self.generate_button.clicked.connect(self._start_generation)
        self.cancel_button.clicked.connect(self._cancel_generation)

        self._restore_state()
        self._refresh_preview()

    # --------------------------------------------------------------- layout

    def _build_layout(self) -> None:
        settings_scroll = QScrollArea()
        settings_scroll.setWidget(self.settings_panel)
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(settings_scroll, 3)
        right_layout.addWidget(self.preview_panel, 2)
        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(self.cancel_button)
        right_layout.addWidget(self.generate_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.image_list)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        self._splitter = splitter

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        add_action = QAction("&Add Images…", self)
        add_action.setShortcut(QKeySequence.StandardKey.Open)
        add_action.triggered.connect(self._add_images_dialog)
        generate_action = QAction("&Generate PDF", self)
        generate_action.triggered.connect(self._start_generation)
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(add_action)
        file_menu.addAction(generate_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About…", self)
        about_action.triggered.connect(lambda: dialogs.show_about(self))
        help_menu.addAction(about_action)

    # ------------------------------------------------------------- add flow

    def _add_images_dialog(self) -> None:
        start_dir = self._qsettings.value("lastImageDir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add images", str(start_dir), _FILE_DIALOG_FILTER
        )
        if not paths:
            return
        self._qsettings.setValue("lastImageDir", str(Path(paths[0]).parent))
        self.image_list.add_images(paths)

    def _refresh_preview(self) -> None:
        settings = self.settings_panel.settings()
        count = self.image_list.count()
        self.preview_panel.update_preview(settings, count)
        if count:
            self.statusBar().showMessage(self.preview_panel.preview.summary_text())

    # ------------------------------------------------------ generation flow

    def _start_generation(self) -> None:
        if self._worker is not None:
            return  # already generating
        settings = self.settings_panel.settings()
        paths = self.image_list.paths()
        captions = self.image_list.captions()
        if not paths:
            dialogs.show_warning(self, "No images", "Add at least one image first.")
            return
        if not settings.output.output_path:
            dialogs.show_warning(
                self, "No output file", "Choose where to save the PDF (Output → Browse)."
            )
            return
        output = Path(settings.output.output_path).expanduser()
        if output.suffix.lower() != ".pdf":
            output = output.with_suffix(".pdf")
            settings.output.output_path = str(output)
        if output.exists() and not dialogs.confirm_overwrite(self, str(output)):
            return

        jobs = [TileJob(path=p, caption=c) for p, c in zip(paths, captions, strict=True)]
        self._worker = PdfWorker(settings, jobs)
        self._worker.progressChanged.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_success)
        self._worker.failed.connect(self._on_failure)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_worker_finished)

        self._set_generating(True)
        self.progress_bar.setRange(0, len(jobs))
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Generating PDF…")
        self._worker.start()

    def _cancel_generation(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("Cancelling…")

    def _set_generating(self, generating: bool) -> None:
        self.generate_button.setVisible(not generating)
        self.progress_bar.setVisible(generating)
        self.cancel_button.setVisible(generating)
        self.cancel_button.setEnabled(True)
        self.image_list.setEnabled(not generating)
        self.settings_panel.setEnabled(not generating)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        self.progress_bar.setFormat(f"{done} / {total} images")

    def _on_success(self, result: GenerationResult) -> None:
        self.statusBar().showMessage(
            f"Created {result.output_path} ({result.page_count} pages)"
        )
        settings = self.settings_panel.settings()
        dialogs.show_generation_success(self, result)
        if settings.output.open_after_generation:
            QDesktopServices.openUrl(QUrl.fromLocalFile(result.output_path))

    def _on_failure(self, message: str) -> None:
        self.statusBar().showMessage("PDF generation failed")
        dialogs.show_error(self, "Could not create PDF", message)

    def _on_cancelled(self) -> None:
        self.statusBar().showMessage("Generation cancelled")

    def _on_worker_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._set_generating(False)

    # ---------------------------------------------------------- persistence

    def _restore_state(self) -> None:
        geometry = self._qsettings.value("windowGeometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter_state = self._qsettings.value("splitterState")
        if splitter_state is not None:
            self._splitter.restoreState(splitter_state)
        raw = self._qsettings.value("projectSettings")
        if raw:
            try:
                self.settings_panel.load(ProjectSettings.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Ignoring corrupt saved settings")
        self.image_list.set_title_case(self.settings_panel.title_case_check.isChecked())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(5000)
        self._qsettings.setValue("windowGeometry", self.saveGeometry())
        self._qsettings.setValue("splitterState", self._splitter.saveState())
        self._qsettings.setValue(
            "projectSettings", json.dumps(self.settings_panel.settings().to_dict())
        )
        super().closeEvent(event)
