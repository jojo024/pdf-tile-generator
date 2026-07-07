"""The image list: table of thumbnail / filename / caption, with reordering.

Captions in the third column are editable; a user-edited caption is marked
"custom" and survives caption regeneration (e.g. when Title Case is toggled).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_tile_generator.captions import generate_caption
from pdf_tile_generator.captions.csv_io import (
    CaptionCSVError,
    lookup,
    read_caption_csv,
    write_caption_csv,
)
from pdf_tile_generator.gui.workers import ThumbnailSignals, ThumbnailTask
from pdf_tile_generator.images.loader import is_supported_image

COL_THUMB = 0
COL_FILENAME = 1
COL_CAPTION = 2
COL_DESCRIPTION = 3
_COLUMN_COUNT = 4  # fixed columns; user-defined extra columns start here
_RESERVED_NAMES = {"preview", "filename", "caption", "description"}

_PATH_ROLE = Qt.ItemDataRole.UserRole
_CUSTOM_CAPTION_ROLE = Qt.ItemDataRole.UserRole + 1


class ImageTable(QTableWidget):
    """Table accepting image-file drops from the OS."""

    filesDropped = Signal(list)  # list[str]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, _COLUMN_COUNT, parent)
        self.setAcceptDrops(True)
        self.setHorizontalHeaderLabels(["Preview", "Filename", "Caption", "Description"])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(72, 72))
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(80)
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_THUMB, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_THUMB, 90)
        header.setSectionResizeMode(COL_FILENAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_CAPTION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        self.setAccessibleName("Selected images")
        self.setToolTip("Drag image files here, or use the Add Images button.")

    @staticmethod
    def _image_paths_from_event(event: QDropEvent) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and is_supported_image(local):
                paths.append(local)
        return paths

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._image_paths_from_event(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001 - Qt override
        if self._image_paths_from_event(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = self._image_paths_from_event(event)
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
        else:
            super().dropEvent(event)


class ImageListWidget(QWidget):
    """Image table plus Add/Remove/Clear/Move controls."""

    listChanged = Signal()  # emitted whenever rows are added/removed/reordered

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title_case = True
        self._updating = False  # guards programmatic caption writes
        self._extra_columns: list[str] = []  # user-defined column names
        self._thumbnail_signals = ThumbnailSignals()
        self._thumbnail_signals.ready.connect(self._on_thumbnail_ready)
        self._thumbnail_signals.failed.connect(self._on_thumbnail_failed)

        self.table = ImageTable(self)
        self.table.filesDropped.connect(self.add_images)
        self.table.itemChanged.connect(self._on_item_changed)

        self.add_button = QPushButton("Add Images…")
        self.remove_button = QPushButton("Remove Selected")
        self.clear_button = QPushButton("Clear All")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")
        self.import_csv_button = QPushButton("Import CSV…")
        self.import_csv_button.setToolTip(
            "Bulk-load captions, descriptions, and extra fields from a CSV file "
            "(filename, caption, description, plus your own column names)"
        )
        self.export_csv_button = QPushButton("Export CSV…")
        self.export_csv_button.setToolTip(
            "Save the current captions, descriptions, and extra columns to a CSV file"
        )
        self.add_column_button = QPushButton("Add Column…")
        self.add_column_button.setToolTip(
            "Add a custom column; its text appears under the tile, below the description"
        )
        self.remove_column_button = QPushButton("Remove Column…")
        self.remove_column_button.setToolTip("Remove one of your custom columns")
        self.remove_button.setToolTip("Remove the selected images from the list")
        self.up_button.setToolTip("Move the selected image up (Alt+Up)")
        self.down_button.setToolTip("Move the selected image down (Alt+Down)")
        self.up_button.setShortcut("Alt+Up")
        self.down_button.setShortcut("Alt+Down")

        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_all)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.import_csv_button.clicked.connect(self._import_csv_dialog)
        self.export_csv_button.clicked.connect(self._export_csv_dialog)
        self.add_column_button.clicked.connect(self._add_column_dialog)
        self.remove_column_button.clicked.connect(self._remove_column_dialog)

        buttons = QHBoxLayout()
        for button in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.up_button,
            self.down_button,
            self.import_csv_button,
            self.export_csv_button,
            self.add_column_button,
            self.remove_column_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

    # ------------------------------------------------------------------ data

    def paths(self) -> list[str]:
        """All image paths in display order."""
        return [
            self.table.item(row, COL_FILENAME).data(_PATH_ROLE)
            for row in range(self.table.rowCount())
        ]

    def captions(self) -> list[str]:
        """All captions in display order."""
        return [self.table.item(row, COL_CAPTION).text() for row in range(self.table.rowCount())]

    def descriptions(self) -> list[str]:
        """All descriptions in display order."""
        return [
            self.table.item(row, COL_DESCRIPTION).text() for row in range(self.table.rowCount())
        ]

    def extra_columns(self) -> list[str]:
        """Names of the user-defined extra columns, in display order."""
        return list(self._extra_columns)

    def extra_values(self) -> list[list[str]]:
        """Per-row values of the extra columns, aligned with extra_columns()."""
        return [
            [
                self.table.item(row, _COLUMN_COUNT + index).text()
                for index in range(len(self._extra_columns))
            ]
            for row in range(self.table.rowCount())
        ]

    # -------------------------------------------------------- extra columns

    def set_extra_columns(self, names: list[str]) -> None:
        """Replace all extra columns (used when restoring saved settings)."""
        for name in list(reversed(self._extra_columns)):
            self.remove_column(name)
        for name in names:
            self.add_column(name)

    def add_column(self, name: str) -> bool:
        """Add a custom column; returns False for empty/duplicate/reserved names."""
        name = name.strip()
        lower = name.lower()
        if not name or lower in _RESERVED_NAMES:
            return False
        if lower in (existing.lower() for existing in self._extra_columns):
            return False
        column = _COLUMN_COUNT + len(self._extra_columns)
        self._extra_columns.append(name)
        self._updating = True
        try:
            self.table.setColumnCount(column + 1)
            header_item = QTableWidgetItem(name)
            self.table.setHorizontalHeaderItem(column, header_item)
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
            for row in range(self.table.rowCount()):
                item = QTableWidgetItem("")
                item.setToolTip(f'"{name}" text shown under the tile (double-click to edit)')
                self.table.setItem(row, column, item)
        finally:
            self._updating = False
        self.listChanged.emit()
        return True

    def remove_column(self, name: str) -> None:
        """Remove a custom column by name."""
        if name not in self._extra_columns:
            return
        index = self._extra_columns.index(name)
        self._extra_columns.pop(index)
        self.table.removeColumn(_COLUMN_COUNT + index)
        self.listChanged.emit()

    def _add_column_dialog(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "Add column",
            "Column name (its text appears under each tile):",
        )
        if not ok or not name.strip():
            return
        if not self.add_column(name):
            QMessageBox.warning(
                self,
                "Cannot add column",
                f'"{name.strip()}" is already used or reserved. Choose another name.',
            )

    def _remove_column_dialog(self) -> None:
        if not self._extra_columns:
            QMessageBox.information(
                self, "No custom columns", "There is no custom column to remove."
            )
            return
        name, ok = QInputDialog.getItem(
            self,
            "Remove column",
            "Custom column to remove (its text is discarded):",
            self._extra_columns,
            0,
            False,
        )
        if ok and name:
            self.remove_column(name)

    def count(self) -> int:
        """Number of images in the list."""
        return self.table.rowCount()

    # ----------------------------------------------------------- list edits

    def add_images(self, paths: list[str]) -> None:
        """Append images (duplicates allowed - users may want repeats)."""
        pool = QThreadPool.globalInstance()
        self._updating = True
        try:
            for raw_path in paths:
                path = str(Path(raw_path))
                row = self.table.rowCount()
                self.table.insertRow(row)

                thumb_item = QTableWidgetItem()
                thumb_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                thumb_item.setText("…")

                name_item = QTableWidgetItem(Path(path).name)
                name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                name_item.setData(_PATH_ROLE, path)
                name_item.setToolTip(path)

                caption_item = QTableWidgetItem(generate_caption(path, self._title_case))
                caption_item.setData(_CUSTOM_CAPTION_ROLE, False)
                caption_item.setToolTip("Double-click to edit this caption")

                description_item = QTableWidgetItem("")
                description_item.setToolTip(
                    "Optional text shown under the caption (double-click to edit)"
                )

                self.table.setItem(row, COL_THUMB, thumb_item)
                self.table.setItem(row, COL_FILENAME, name_item)
                self.table.setItem(row, COL_CAPTION, caption_item)
                self.table.setItem(row, COL_DESCRIPTION, description_item)
                for index, column_name in enumerate(self._extra_columns):
                    item = QTableWidgetItem("")
                    item.setToolTip(
                        f'"{column_name}" text shown under the tile (double-click to edit)'
                    )
                    self.table.setItem(row, _COLUMN_COUNT + index, item)
                pool.start(ThumbnailTask(path, self._thumbnail_signals))
        finally:
            self._updating = False
        self.listChanged.emit()

    def remove_selected(self) -> None:
        """Remove all selected rows."""
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.listChanged.emit()

    def clear_all(self) -> None:
        """Remove every image."""
        if self.table.rowCount():
            self.table.setRowCount(0)
            self.listChanged.emit()

    def _move_selected(self, delta: int) -> None:
        """Move the selected rows up (delta=-1) or down (delta=+1) by one."""
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not rows:
            return
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == self.table.rowCount() - 1:
            return
        ordered = rows if delta < 0 else list(reversed(rows))
        self._updating = True
        try:
            for row in ordered:
                self._swap_rows(row, row + delta)
        finally:
            self._updating = False
        self.table.clearSelection()
        for row in rows:
            for column in range(self.table.columnCount()):
                self.table.item(row + delta, column).setSelected(True)
        self.listChanged.emit()

    def _swap_rows(self, row_a: int, row_b: int) -> None:
        for column in range(self.table.columnCount()):
            item_a = self.table.takeItem(row_a, column)
            item_b = self.table.takeItem(row_b, column)
            self.table.setItem(row_a, column, item_b)
            self.table.setItem(row_b, column, item_a)

    # ------------------------------------------------------------- captions

    def set_title_case(self, title_case: bool) -> None:
        """Regenerate all non-custom captions with the new Title Case setting."""
        self._title_case = title_case
        self._updating = True
        try:
            for row in range(self.table.rowCount()):
                caption_item = self.table.item(row, COL_CAPTION)
                if caption_item.data(_CUSTOM_CAPTION_ROLE):
                    continue  # keep the user's hand-edited caption
                path = self.table.item(row, COL_FILENAME).data(_PATH_ROLE)
                caption_item.setText(generate_caption(path, title_case))
        finally:
            self._updating = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != COL_CAPTION:
            return
        item.setData(_CUSTOM_CAPTION_ROLE, True)

    # ------------------------------------------------------------ CSV bulk

    def apply_csv(self, path: str) -> int:
        """Apply captions/descriptions/extra fields from a CSV; returns rows matched.

        Unknown CSV columns are added as new extra columns automatically, so a
        spreadsheet with e.g. a "Location" column just works.

        Raises:
            CaptionCSVError: if the file is unreadable or malformed.
        """
        data = read_caption_csv(path)
        for name in data.extra_fields:
            if name.lower() not in (existing.lower() for existing in self._extra_columns):
                self.add_column(name)
        column_by_lower = {
            name.lower(): _COLUMN_COUNT + index
            for index, name in enumerate(self._extra_columns)
        }
        matched = 0
        self._updating = True
        try:
            for row in range(self.table.rowCount()):
                image_path = self.table.item(row, COL_FILENAME).data(_PATH_ROLE)
                entry = lookup(data, image_path)
                if entry is None:
                    continue
                matched += 1
                if entry.caption is not None:
                    caption_item = self.table.item(row, COL_CAPTION)
                    caption_item.setText(entry.caption)
                    caption_item.setData(_CUSTOM_CAPTION_ROLE, True)
                if entry.description is not None:
                    self.table.item(row, COL_DESCRIPTION).setText(entry.description)
                for field_name, value in entry.extras.items():
                    if value is not None and field_name in column_by_lower:
                        self.table.item(row, column_by_lower[field_name]).setText(value)
        finally:
            self._updating = False
        return matched

    def _import_csv_dialog(self) -> None:
        if not self.count():
            QMessageBox.information(
                self, "No images", "Add images first, then import their captions."
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import captions CSV", "", "CSV files (*.csv);;All files (*.*)"
        )
        if not path:
            return
        try:
            matched = self.apply_csv(path)
        except CaptionCSVError as exc:
            QMessageBox.warning(self, "Could not import CSV", str(exc))
            return
        QMessageBox.information(
            self,
            "CSV imported",
            f"Updated {matched} of {self.count()} images "
            f"(matched by filename).",
        )

    def _export_csv_dialog(self) -> None:
        if not self.count():
            QMessageBox.information(self, "No images", "There is nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export captions CSV", "captions.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        entries = list(
            zip(
                self.paths(),
                self.captions(),
                self.descriptions(),
                self.extra_values(),
                strict=True,
            )
        )
        try:
            write_caption_csv(path, entries, extra_fields=self.extra_columns())
        except CaptionCSVError as exc:
            QMessageBox.warning(self, "Could not export CSV", str(exc))

    # ----------------------------------------------------------- thumbnails

    def _rows_for_path(self, path: str) -> list[int]:
        return [
            row
            for row in range(self.table.rowCount())
            if self.table.item(row, COL_FILENAME).data(_PATH_ROLE) == path
        ]

    def _on_thumbnail_ready(self, path: str, image: QImage) -> None:
        icon = QIcon(QPixmap.fromImage(image))
        for row in self._rows_for_path(path):
            item = self.table.item(row, COL_THUMB)
            item.setText("")
            item.setIcon(icon)

    def _on_thumbnail_failed(self, path: str, message: str) -> None:
        for row in self._rows_for_path(path):
            item = self.table.item(row, COL_THUMB)
            item.setText("⚠")
            item.setToolTip(message)
