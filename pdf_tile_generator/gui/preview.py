"""Live page-layout preview.

Draws a scaled diagram of one page: tile outlines, image areas, and caption
placeholder lines, plus a summary of tiles per page and total page count.
This is a diagram (not a pixel-accurate render), which keeps it instant even
with 500+ images loaded.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pdf_tile_generator.models.settings import ProjectSettings
from pdf_tile_generator.pdf.layout import LayoutError, compute_page_tiles, page_count


class PagePreview(QWidget):
    """Scaled diagram of the first page's tile layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = ProjectSettings()
        self._image_count = 0
        self._error: str | None = None
        self.setMinimumSize(180, 220)
        self.setAccessibleName("Page layout preview")

    def update_preview(self, settings: ProjectSettings, image_count: int) -> None:
        """Recompute the diagram for new settings or image count."""
        self._settings = settings
        self._image_count = image_count
        try:
            compute_page_tiles(settings.page, settings.layout, settings.caption)
            self._error = None
        except LayoutError as exc:
            self._error = str(exc)
        self.update()

    def summary_text(self) -> str:
        """Human-readable layout summary for the label under the diagram."""
        if self._error:
            return f"⚠ {self._error}"
        try:
            tiles = compute_page_tiles(
                self._settings.page, self._settings.layout, self._settings.caption
            )
        except LayoutError as exc:
            return f"⚠ {exc}"
        pages = page_count(self._image_count, len(tiles))
        if self._image_count == 0:
            return f"{len(tiles)} tiles per page — add images to begin"
        plural = "s" if pages != 1 else ""
        return (
            f"{len(tiles)} tiles per page — {self._image_count} images "
            f"→ {pages} page{plural}"
        )

    def paintEvent(self, event) -> None:  # noqa: ANN001 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        page_w, page_h = self._settings.page.page_size
        available_w = self.width() - 16
        available_h = self.height() - 16
        scale = min(available_w / page_w, available_h / page_h)
        draw_w = page_w * scale
        draw_h = page_h * scale
        offset_x = (self.width() - draw_w) / 2
        offset_y = (self.height() - draw_h) / 2

        # Page sheet with a subtle shadow.
        painter.fillRect(QRectF(offset_x + 3, offset_y + 3, draw_w, draw_h), QColor(0, 0, 0, 40))
        painter.fillRect(QRectF(offset_x, offset_y, draw_w, draw_h), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.drawRect(QRectF(offset_x, offset_y, draw_w, draw_h))

        if self._error:
            painter.setPen(QPen(QColor("#cc4444"), 2))
            painter.drawLine(
                QRectF(offset_x, offset_y, draw_w, draw_h).topLeft(),
                QRectF(offset_x, offset_y, draw_w, draw_h).bottomRight(),
            )
            painter.end()
            return

        try:
            tiles = compute_page_tiles(
                self._settings.page, self._settings.layout, self._settings.caption
            )
        except LayoutError:
            painter.end()
            return

        image_brush = QColor("#b8cfe8")
        caption_pen = QPen(QColor("#777777"), 1)
        border_pen = QPen(QColor("#6688aa"), 1)
        for tile in tiles:
            # Convert bottom-left PDF coordinates to top-left Qt coordinates.
            tile_left = offset_x + tile.x * scale
            image_top = offset_y + (page_h - (tile.image_y + tile.image_height)) * scale
            image_rect = QRectF(
                tile_left, image_top, tile.width * scale, tile.image_height * scale
            )
            painter.setPen(border_pen)
            painter.fillRect(image_rect, image_brush)
            painter.drawRect(image_rect)
            # Caption placeholder: a centered line under the image.
            caption_y = image_rect.bottom() + max(
                2.0, self._settings.page.caption_spacing * scale
            )
            painter.setPen(caption_pen)
            line_half = tile.width * scale * 0.3
            center_x = tile_left + tile.width * scale / 2
            painter.drawLine(
                int(center_x - line_half), int(caption_y), int(center_x + line_half), int(caption_y)
            )
        painter.end()


class PreviewPanel(QWidget):
    """Preview diagram plus its summary label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview = PagePreview(self)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.summary)

    def update_preview(self, settings: ProjectSettings, image_count: int) -> None:
        self.preview.update_preview(settings, image_count)
        self.summary.setText(self.preview.summary_text())
