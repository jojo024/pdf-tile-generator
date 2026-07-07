"""Tests for user-defined extra columns rendered under tiles (v1.2.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_tile_generator.captions.csv_io import (
    lookup,
    read_caption_csv,
    write_caption_csv,
)
from pdf_tile_generator.models.settings import CaptionSettings, OutputSettings, ProjectSettings
from pdf_tile_generator.pdf.generator import PDFGenerator, TileJob


class TestBlockHeight:
    def test_grows_per_extra_field(self) -> None:
        base = CaptionSettings().block_height()
        one = CaptionSettings(extra_fields=["Location"]).block_height()
        two = CaptionSettings(extra_fields=["Location", "Client"]).block_height()
        assert one > base
        assert two - one == pytest.approx(one - base)

    def test_round_trips(self) -> None:
        settings = ProjectSettings()
        settings.caption.extra_fields = ["Location", "Client"]
        restored = ProjectSettings.from_dict(settings.to_dict())
        assert restored.caption.extra_fields == ["Location", "Client"]

    def test_malformed_extra_fields_ignored(self) -> None:
        data = ProjectSettings().to_dict()
        data["caption"]["extra_fields"] = "not-a-list"
        assert ProjectSettings.from_dict(data).caption.extra_fields == []


class TestCsvExtras:
    def test_round_trip_with_extras(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "extras.csv"
        write_caption_csv(
            csv_path,
            [
                ("a.jpg", "Cap A", "Desc A", ["First floor", "ACME"]),
                ("b.jpg", "Cap B", "", ["Basement", ""]),
            ],
            extra_fields=["Location", "Client"],
        )
        data = read_caption_csv(csv_path)
        assert data.extra_fields == ["Location", "Client"]
        entry = lookup(data, r"C:\anywhere\a.jpg")
        assert entry is not None
        assert entry.extras == {"location": "First floor", "client": "ACME"}
        entry_b = lookup(data, "b.jpg")
        assert entry_b is not None
        assert entry_b.extras["client"] is None  # empty cell -> leave unchanged

    def test_unknown_headers_become_extra_fields(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "sheet.csv"
        csv_path.write_text(
            "filename,caption,Location\na.jpg,Hello,Roof\n", encoding="utf-8"
        )
        data = read_caption_csv(csv_path)
        assert data.extra_fields == ["Location"]
        entry = lookup(data, "a.jpg")
        assert entry is not None
        assert entry.extras == {"location": "Roof"}

    def test_reserved_headers_not_extras(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "r.csv"
        csv_path.write_text(
            "filename,CAPTION,Description,Notes\na.jpg,X,Y,Z\n", encoding="utf-8"
        )
        data = read_caption_csv(csv_path)
        assert data.extra_fields == ["Notes"]

    def test_short_entries_padded_on_write(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "pad.csv"
        write_caption_csv(
            csv_path, [("a.jpg", "Cap", "Desc")], extra_fields=["Location"]
        )
        header, row = csv_path.read_text(encoding="utf-8-sig").strip().splitlines()
        assert header.count(",") == row.count(",")


class TestPdfWithExtras:
    def test_generates_valid_pdf(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "extras.pdf"
        settings = ProjectSettings(output=OutputSettings(output_path=str(output)))
        settings.caption.extra_fields = ["Location", "Client"]
        jobs = [
            TileJob(
                path=str(p),
                caption=p.stem,
                description="A description",
                extras=[f"Floor {i}", "ACME Ltd"],
            )
            for i, p in enumerate(sample_images)
        ]
        result = PDFGenerator(settings).generate(jobs)
        assert result.image_count == len(sample_images)
        assert output.read_bytes().startswith(b"%PDF-")

    def test_extras_without_caption_or_description(
        self, sample_images: list[Path], tmp_path: Path
    ) -> None:
        output = tmp_path / "only_extras.pdf"
        settings = ProjectSettings(output=OutputSettings(output_path=str(output)))
        settings.caption.extra_fields = ["Note"]
        jobs = [TileJob(path=str(sample_images[0]), caption="", extras=["Just a note"])]
        assert PDFGenerator(settings).generate(jobs).image_count == 1

    def test_empty_extras_list_ok(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "no_extras.pdf"
        settings = ProjectSettings(output=OutputSettings(output_path=str(output)))
        jobs = [TileJob(path=str(p), caption=p.stem) for p in sample_images]
        assert PDFGenerator(settings).generate(jobs).image_count == len(sample_images)
