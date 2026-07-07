"""CSV import/export of captions, descriptions, and extra fields.

Format (header required, order-insensitive):

    filename,caption,description,Location,Client
    living_room_01.jpg,Living Room,South-facing,First floor,ACME Ltd

``filename``, ``caption``, and ``description`` are reserved column names; any
other non-empty header is treated as a user-defined extra field and becomes
an extra column in the image list on import.

Rows are matched to images by filename (case-insensitive), so a CSV written
on one machine applies cleanly on another even if the folders differ.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

RESERVED_FIELDS = ("filename", "caption", "description")


class CaptionCSVError(Exception):
    """A user-presentable CSV problem."""


@dataclass(frozen=True)
class CsvRow:
    """One row of caption data keyed by filename."""

    filename: str
    caption: str | None  # None = column absent / cell empty -> leave unchanged
    description: str | None
    extras: dict[str, str | None] = field(default_factory=dict)  # lowercase field name -> value


@dataclass(frozen=True)
class CsvData:
    """Everything read from a caption CSV."""

    rows: dict[str, CsvRow]  # normalized filename -> row
    extra_fields: list[str]  # non-reserved header names, in file order


def _normalize_key(filename: str) -> str:
    """Matching key: basename, lowercased, both separators honored."""
    return filename.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()


def read_caption_csv(path: str | Path) -> CsvData:
    """Read a caption CSV.

    Empty cells become ``None`` (meaning "leave the current value
    unchanged") so a partial CSV can update only some fields. Non-reserved
    headers are collected as extra fields.

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
                    'The CSV needs a "filename" column (plus "caption", '
                    '"description", or your own field names).'
                )
            extra_fields = [
                name.strip()
                for name in reader.fieldnames
                if name and name.strip() and name.strip().lower() not in RESERVED_FIELDS
            ]

            def cell(record: dict, lower_name: str) -> str | None:
                value = record.get(fields.get(lower_name, ""))
                return value.strip() if value and value.strip() else None

            rows: dict[str, CsvRow] = {}
            for record in reader:
                filename = (record.get(fields["filename"]) or "").strip()
                if not filename:
                    continue
                rows[_normalize_key(filename)] = CsvRow(
                    filename=filename,
                    caption=cell(record, "caption"),
                    description=cell(record, "description"),
                    extras={name.lower(): cell(record, name.lower()) for name in extra_fields},
                )
            return CsvData(rows=rows, extra_fields=extra_fields)
    except OSError as exc:
        raise CaptionCSVError(f"Could not read the CSV file: {file_path.name}") from exc
    except csv.Error as exc:
        raise CaptionCSVError(f"The CSV file is malformed: {file_path.name}") from exc


def write_caption_csv(
    path: str | Path,
    entries: list[tuple],
    extra_fields: list[str] | None = None,
) -> None:
    """Write caption entries to a CSV file.

    Each entry is ``(path, caption, description)`` optionally followed by a
    list of extra-field values matching ``extra_fields`` in order.

    Raises:
        CaptionCSVError: if the file cannot be written.
    """
    file_path = Path(path)
    extra_fields = extra_fields or []
    try:
        with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["filename", "caption", "description", *extra_fields])
            for entry in entries:
                image_path, caption, description, *rest = entry
                extras = list(rest[0]) if rest else []
                extras += [""] * (len(extra_fields) - len(extras))
                name = image_path.replace("\\", "/").rsplit("/", 1)[-1]
                writer.writerow([name, caption, description, *extras])
    except OSError as exc:
        raise CaptionCSVError(f"Could not write the CSV file: {file_path.name}") from exc


def lookup(data: CsvData, image_path: str) -> CsvRow | None:
    """Find the CSV row for an image path, matching by normalized basename."""
    return data.rows.get(_normalize_key(image_path))
