"""CSV import/export of captions and descriptions.

Format (header required, extra columns ignored, order-insensitive):

    filename,caption,description
    living_room_01.jpg,Living Room,South-facing with bay windows

Rows are matched to images by filename (case-insensitive), so a CSV written
on one machine applies cleanly on another even if the folders differ.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class CaptionCSVError(Exception):
    """A user-presentable CSV problem."""


@dataclass(frozen=True)
class CsvRow:
    """One row of caption data keyed by filename."""

    filename: str
    caption: str | None  # None = column absent / cell empty -> leave unchanged
    description: str | None


def _normalize_key(filename: str) -> str:
    """Matching key: basename, lowercased, both separators honored."""
    return filename.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()


def read_caption_csv(path: str | Path) -> dict[str, CsvRow]:
    """Read a caption CSV into a mapping of normalized filename -> row.

    Empty caption/description cells become ``None`` (meaning "leave the
    current value unchanged") so a partial CSV can update only captions or
    only descriptions.

    Raises:
        CaptionCSVError: if the file cannot be read or has no ``filename``
            column.
    """
    file_path = Path(path)
    try:
        with open(file_path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise CaptionCSVError("The CSV file is empty.")
            fields = {name.strip().lower(): name for name in reader.fieldnames if name}
            if "filename" not in fields:
                raise CaptionCSVError(
                    'The CSV needs a "filename" column (plus "caption" and/or '
                    '"description").'
                )
            rows: dict[str, CsvRow] = {}
            for record in reader:
                filename = (record.get(fields["filename"]) or "").strip()
                if not filename:
                    continue
                caption = record.get(fields.get("caption", ""), None)
                description = record.get(fields.get("description", ""), None)
                rows[_normalize_key(filename)] = CsvRow(
                    filename=filename,
                    caption=caption.strip() if caption and caption.strip() else None,
                    description=(
                        description.strip() if description and description.strip() else None
                    ),
                )
            return rows
    except OSError as exc:
        raise CaptionCSVError(f"Could not read the CSV file: {file_path.name}") from exc
    except csv.Error as exc:
        raise CaptionCSVError(f"The CSV file is malformed: {file_path.name}") from exc


def write_caption_csv(
    path: str | Path, entries: list[tuple[str, str, str]]
) -> None:
    """Write ``(path, caption, description)`` entries to a CSV file.

    Raises:
        CaptionCSVError: if the file cannot be written.
    """
    file_path = Path(path)
    try:
        with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["filename", "caption", "description"])
            for image_path, caption, description in entries:
                name = image_path.replace("\\", "/").rsplit("/", 1)[-1]
                writer.writerow([name, caption, description])
    except OSError as exc:
        raise CaptionCSVError(f"Could not write the CSV file: {file_path.name}") from exc


def lookup(rows: dict[str, CsvRow], image_path: str) -> CsvRow | None:
    """Find the CSV row for an image path, matching by normalized basename."""
    return rows.get(_normalize_key(image_path))
