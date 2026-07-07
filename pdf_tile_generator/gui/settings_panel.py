"""Settings side panel: layout, page, image, caption, and output options.

The panel displays dimensions in millimeters (friendlier than points) and
converts to points when building the :class:`ProjectSettings` model.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdf_tile_generator.models.settings import (
    CAPTION_FONTS,
    PAPER_AUTO,
    PAPER_CUSTOM,
    PAPER_SIZES,
    CaptionSettings,
    ImageFitMode,
    ImageSettings,
    LayoutSettings,
    OutputSettings,
    PageSettings,
    ProjectSettings,
    TextAlignment,
)

MM_TO_PT = 72.0 / 25.4


def _mm(points: float) -> float:
    return points / MM_TO_PT


def _pt(millimeters: float) -> float:
    return millimeters * MM_TO_PT


def _mm_spin(minimum: float, maximum: float, tooltip: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(1)
    spin.setSingleStep(1.0)
    spin.setSuffix(" mm")
    spin.setToolTip(tooltip)
    return spin


class SettingsPanel(QWidget):
    """Editable view of a :class:`ProjectSettings`."""

    settingsChanged = Signal()
    titleCaseChanged = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caption_color = QColor("#000000")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_layout_group())
        layout.addWidget(self._build_page_group())
        layout.addWidget(self._build_image_group())
        layout.addWidget(self._build_caption_group())
        layout.addWidget(self._build_output_group())
        layout.addStretch(1)

    # ------------------------------------------------------------- builders

    def _build_layout_group(self) -> QGroupBox:
        group = QGroupBox("Grid Layout")
        self.grid_radio = QRadioButton("Rows × Columns")
        self.grid_radio.setChecked(True)
        self.auto_radio = QRadioButton("Images per page (automatic grid)")
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 12)
        self.rows_spin.setValue(3)
        self.rows_spin.setToolTip("Number of tile rows on each page")
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 12)
        self.cols_spin.setValue(2)
        self.cols_spin.setToolTip("Number of tile columns on each page")
        self.per_page_spin = QSpinBox()
        self.per_page_spin.setRange(1, 64)
        self.per_page_spin.setValue(6)
        self.per_page_spin.setToolTip("The grid is chosen automatically for this many images")
        self.per_page_spin.setEnabled(False)

        outer = QVBoxLayout(group)
        outer.addWidget(self.grid_radio)
        form = QFormLayout()
        form.addRow("Rows:", self.rows_spin)
        form.addRow("Columns:", self.cols_spin)
        outer.addLayout(form)
        outer.addWidget(self.auto_radio)
        per_form = QFormLayout()
        per_form.addRow("Images per page:", self.per_page_spin)
        outer.addLayout(per_form)

        def sync_enabled() -> None:
            auto = self.auto_radio.isChecked()
            self.rows_spin.setEnabled(not auto)
            self.cols_spin.setEnabled(not auto)
            self.per_page_spin.setEnabled(auto)

        for widget in (self.grid_radio, self.auto_radio):
            widget.toggled.connect(sync_enabled)
            widget.toggled.connect(self._emit_changed)
        for spin in (self.rows_spin, self.cols_spin, self.per_page_spin):
            spin.valueChanged.connect(self._emit_changed)
        return group

    def _build_page_group(self) -> QGroupBox:
        group = QGroupBox("Page")
        self.paper_combo = QComboBox()
        self.paper_combo.addItems([*PAPER_SIZES.keys(), PAPER_CUSTOM, PAPER_AUTO])
        self.paper_combo.setToolTip(
            "Paper size of the generated PDF. Custom: enter exact dimensions. "
            "Auto: the page grows to fit the grid at your chosen tile size, so "
            "large grids keep full-size tiles instead of shrinking."
        )
        self.custom_width_spin = _mm_spin(30, 2000, "Custom page width")
        self.custom_width_spin.setValue(_mm(595.2756))
        self.custom_height_spin = _mm_spin(30, 2000, "Custom page height")
        self.custom_height_spin.setValue(_mm(841.8898))
        self.tile_width_spin = _mm_spin(20, 400, "Tile width when the page size is Auto")
        self.tile_width_spin.setValue(_mm(226.77))
        self.tile_height_spin = _mm_spin(
            20, 400, "Height of each tile's image area when the page size is Auto"
        )
        self.tile_height_spin.setValue(_mm(170.08))
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Portrait", "Landscape"])
        self.margin_spin = _mm_spin(0, 100, "Blank border around the page edge")
        self.margin_spin.setValue(_mm(36.0))
        self.spacing_x_spin = _mm_spin(0, 100, "Horizontal gap between tiles")
        self.spacing_x_spin.setValue(_mm(12.0))
        self.spacing_y_spin = _mm_spin(0, 100, "Vertical gap between tiles")
        self.spacing_y_spin.setValue(_mm(12.0))
        self.caption_spacing_spin = _mm_spin(0, 50, "Gap between an image and its caption")
        self.caption_spacing_spin.setValue(_mm(4.0))

        form = QFormLayout(group)
        form.addRow("Paper size:", self.paper_combo)
        form.addRow("Custom width:", self.custom_width_spin)
        form.addRow("Custom height:", self.custom_height_spin)
        form.addRow("Auto tile width:", self.tile_width_spin)
        form.addRow("Auto tile height:", self.tile_height_spin)
        form.addRow("Orientation:", self.orientation_combo)
        form.addRow("Margins:", self.margin_spin)
        form.addRow("Tile spacing (horizontal):", self.spacing_x_spin)
        form.addRow("Tile spacing (vertical):", self.spacing_y_spin)
        form.addRow("Caption spacing:", self.caption_spacing_spin)

        def sync_paper_mode() -> None:
            paper = self.paper_combo.currentText()
            self.custom_width_spin.setEnabled(paper == PAPER_CUSTOM)
            self.custom_height_spin.setEnabled(paper == PAPER_CUSTOM)
            self.tile_width_spin.setEnabled(paper == PAPER_AUTO)
            self.tile_height_spin.setEnabled(paper == PAPER_AUTO)
            # Orientation is meaningless when dimensions are explicit or derived.
            self.orientation_combo.setEnabled(paper not in (PAPER_CUSTOM, PAPER_AUTO))

        self._sync_paper_mode = sync_paper_mode
        sync_paper_mode()
        self.paper_combo.currentIndexChanged.connect(sync_paper_mode)
        self.paper_combo.currentIndexChanged.connect(self._emit_changed)
        self.orientation_combo.currentIndexChanged.connect(self._emit_changed)
        for spin in (
            self.custom_width_spin,
            self.custom_height_spin,
            self.tile_width_spin,
            self.tile_height_spin,
            self.margin_spin,
            self.spacing_x_spin,
            self.spacing_y_spin,
            self.caption_spacing_spin,
        ):
            spin.valueChanged.connect(self._emit_changed)
        return group

    def _build_image_group(self) -> QGroupBox:
        group = QGroupBox("Images")
        self.fit_combo = QComboBox()
        self.fit_combo.addItem("Fit within tile (no cropping)", ImageFitMode.FIT.value)
        self.fit_combo.addItem("Crop to fill tile", ImageFitMode.CROP.value)
        self.fit_combo.setToolTip(
            "Fit keeps the whole image visible; Crop fills the tile completely "
            "by trimming the edges. Aspect ratio is always preserved."
        )
        self.padding_spin = _mm_spin(0, 30, "Padding inside each tile")
        self.padding_spin.setValue(_mm(4.0))
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Draft (150 DPI, small file)", 150)
        self.quality_combo.addItem("Print (300 DPI, recommended)", 300)
        self.quality_combo.addItem("Maximum (600 DPI, large file)", 600)
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setToolTip("Resolution used when embedding images in the PDF")

        form = QFormLayout(group)
        form.addRow("Placement:", self.fit_combo)
        form.addRow("Tile padding:", self.padding_spin)
        form.addRow("Quality:", self.quality_combo)

        self.fit_combo.currentIndexChanged.connect(self._emit_changed)
        self.quality_combo.currentIndexChanged.connect(self._emit_changed)
        self.padding_spin.valueChanged.connect(self._emit_changed)
        return group

    def _build_caption_group(self) -> QGroupBox:
        group = QGroupBox("Captions")
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(CAPTION_FONTS.keys()))
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setRange(5, 36)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setDecimals(1)
        self.font_size_spin.setSuffix(" pt")
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItem("Center", TextAlignment.CENTER.value)
        self.alignment_combo.addItem("Left", TextAlignment.LEFT.value)
        self.alignment_combo.addItem("Right", TextAlignment.RIGHT.value)
        self.color_button = QPushButton()
        self.color_button.setToolTip("Caption text color")
        self.color_button.setAccessibleName("Caption color")
        self.color_button.clicked.connect(self._pick_color)
        self._apply_color_button()
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(1, 5)
        self.max_lines_spin.setValue(2)
        self.max_lines_spin.setToolTip("Longer captions are truncated with …")
        self.wrap_check = QCheckBox("Wrap long captions")
        self.wrap_check.setChecked(True)
        self.title_case_check = QCheckBox("Title Case captions")
        self.title_case_check.setChecked(True)
        self.title_case_check.setToolTip(
            'Capitalize caption words: "living_room.jpg" becomes "Living Room"'
        )
        self.description_check = QCheckBox("Show descriptions under captions")
        self.description_check.setChecked(True)
        self.description_check.setToolTip(
            "Render the per-image Description column beneath each caption"
        )
        self.description_size_spin = QDoubleSpinBox()
        self.description_size_spin.setRange(5, 24)
        self.description_size_spin.setValue(8)
        self.description_size_spin.setDecimals(1)
        self.description_size_spin.setSuffix(" pt")
        self.description_lines_spin = QSpinBox()
        self.description_lines_spin.setRange(1, 6)
        self.description_lines_spin.setValue(2)

        form = QFormLayout(group)
        form.addRow("Font:", self.font_combo)
        form.addRow("Size:", self.font_size_spin)
        form.addRow("Alignment:", self.alignment_combo)
        form.addRow("Color:", self.color_button)
        form.addRow("Maximum lines:", self.max_lines_spin)
        form.addRow(self.wrap_check)
        form.addRow(self.title_case_check)
        form.addRow(self.description_check)
        form.addRow("Description size:", self.description_size_spin)
        form.addRow("Description lines:", self.description_lines_spin)

        self.font_combo.currentIndexChanged.connect(self._emit_changed)
        self.alignment_combo.currentIndexChanged.connect(self._emit_changed)
        self.font_size_spin.valueChanged.connect(self._emit_changed)
        self.max_lines_spin.valueChanged.connect(self._emit_changed)
        self.wrap_check.toggled.connect(self._emit_changed)
        self.title_case_check.toggled.connect(self._emit_changed)
        self.title_case_check.toggled.connect(self.titleCaseChanged.emit)
        self.description_check.toggled.connect(self._emit_changed)
        self.description_size_spin.valueChanged.connect(self._emit_changed)
        self.description_lines_spin.valueChanged.connect(self._emit_changed)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the PDF…")
        self.output_edit.setToolTip("Full path of the PDF file to create")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_output)
        self.open_after_check = QCheckBox("Open PDF after generation")
        self.open_after_check.setChecked(True)

        row = QHBoxLayout()
        row.addWidget(self.output_edit, 1)
        row.addWidget(browse)
        form = QVBoxLayout(group)
        form.addLayout(row)
        form.addWidget(self.open_after_check)

        self.output_edit.textChanged.connect(self._emit_changed)
        self.open_after_check.toggled.connect(self._emit_changed)
        return group

    # -------------------------------------------------------------- helpers

    def _emit_changed(self, *_: object) -> None:
        self.settingsChanged.emit()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._caption_color, self, "Caption color")
        if color.isValid():
            self._caption_color = color
            self._apply_color_button()
            self._emit_changed()

    def _apply_color_button(self) -> None:
        self.color_button.setText(self._caption_color.name())
        palette = self.color_button.palette()
        palette.setColor(QPalette.ColorRole.ButtonText, self._caption_color)
        self.color_button.setPalette(palette)

    def _browse_output(self) -> None:
        current = self.output_edit.text().strip()
        start_dir = str(Path(current).parent) if current else str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF as…", start_dir, "PDF files (*.pdf)"
        )
        if path:
            self.output_edit.setText(path)

    # --------------------------------------------------------- model bridge

    def settings(self) -> ProjectSettings:
        """Build a :class:`ProjectSettings` from the current widget state."""
        return ProjectSettings(
            page=PageSettings(
                paper_size=self.paper_combo.currentText(),
                landscape=self.orientation_combo.currentText() == "Landscape",
                margin=_pt(self.margin_spin.value()),
                spacing_x=_pt(self.spacing_x_spin.value()),
                spacing_y=_pt(self.spacing_y_spin.value()),
                caption_spacing=_pt(self.caption_spacing_spin.value()),
                custom_width=_pt(self.custom_width_spin.value()),
                custom_height=_pt(self.custom_height_spin.value()),
                auto_tile_width=_pt(self.tile_width_spin.value()),
                auto_tile_image_height=_pt(self.tile_height_spin.value()),
            ),
            layout=LayoutSettings(
                auto_layout=self.auto_radio.isChecked(),
                rows=self.rows_spin.value(),
                columns=self.cols_spin.value(),
                images_per_page=self.per_page_spin.value(),
            ),
            image=ImageSettings(
                fit_mode=ImageFitMode(self.fit_combo.currentData()),
                tile_padding=_pt(self.padding_spin.value()),
                max_render_dpi=int(self.quality_combo.currentData()),
            ),
            caption=CaptionSettings(
                font=self.font_combo.currentText(),
                font_size=self.font_size_spin.value(),
                alignment=TextAlignment(self.alignment_combo.currentData()),
                color=self._caption_color.name(),
                max_lines=self.max_lines_spin.value(),
                wrap_text=self.wrap_check.isChecked(),
                title_case=self.title_case_check.isChecked(),
                description_enabled=self.description_check.isChecked(),
                description_font_size=self.description_size_spin.value(),
                description_max_lines=self.description_lines_spin.value(),
            ),
            output=OutputSettings(
                output_path=self.output_edit.text().strip(),
                open_after_generation=self.open_after_check.isChecked(),
            ),
        )

    def load(self, settings: ProjectSettings) -> None:
        """Populate the widgets from a :class:`ProjectSettings`."""
        blockers = [w for w in self.findChildren(QWidget)]
        for widget in blockers:
            widget.blockSignals(True)
        try:
            if self.paper_combo.findText(settings.page.paper_size) < 0:
                settings.page.paper_size = "A4"  # unknown stored value
            self.paper_combo.setCurrentText(settings.page.paper_size)
            self.orientation_combo.setCurrentText(
                "Landscape" if settings.page.landscape else "Portrait"
            )
            self.custom_width_spin.setValue(_mm(settings.page.custom_width))
            self.custom_height_spin.setValue(_mm(settings.page.custom_height))
            self.tile_width_spin.setValue(_mm(settings.page.auto_tile_width))
            self.tile_height_spin.setValue(_mm(settings.page.auto_tile_image_height))
            self.margin_spin.setValue(_mm(settings.page.margin))
            self.spacing_x_spin.setValue(_mm(settings.page.spacing_x))
            self.spacing_y_spin.setValue(_mm(settings.page.spacing_y))
            self.caption_spacing_spin.setValue(_mm(settings.page.caption_spacing))

            self.auto_radio.setChecked(settings.layout.auto_layout)
            self.grid_radio.setChecked(not settings.layout.auto_layout)
            self.rows_spin.setValue(settings.layout.rows)
            self.cols_spin.setValue(settings.layout.columns)
            self.per_page_spin.setValue(settings.layout.images_per_page)
            self.rows_spin.setEnabled(not settings.layout.auto_layout)
            self.cols_spin.setEnabled(not settings.layout.auto_layout)
            self.per_page_spin.setEnabled(settings.layout.auto_layout)

            index = self.fit_combo.findData(settings.image.fit_mode.value)
            self.fit_combo.setCurrentIndex(max(0, index))
            self.padding_spin.setValue(_mm(settings.image.tile_padding))
            index = self.quality_combo.findData(settings.image.max_render_dpi)
            self.quality_combo.setCurrentIndex(1 if index < 0 else index)

            self.font_combo.setCurrentText(settings.caption.font)
            self.font_size_spin.setValue(settings.caption.font_size)
            index = self.alignment_combo.findData(settings.caption.alignment.value)
            self.alignment_combo.setCurrentIndex(max(0, index))
            color = QColor(settings.caption.color)
            self._caption_color = color if color.isValid() else QColor("#000000")
            self._apply_color_button()
            self.max_lines_spin.setValue(settings.caption.max_lines)
            self.wrap_check.setChecked(settings.caption.wrap_text)
            self.title_case_check.setChecked(settings.caption.title_case)
            self.description_check.setChecked(settings.caption.description_enabled)
            self.description_size_spin.setValue(settings.caption.description_font_size)
            self.description_lines_spin.setValue(settings.caption.description_max_lines)

            self.output_edit.setText(settings.output.output_path)
            self.open_after_check.setChecked(settings.output.open_after_generation)
        finally:
            for widget in blockers:
                widget.blockSignals(False)
        self._sync_paper_mode()
        self.settingsChanged.emit()
