"""Tests for v1.1.0 features: auto/custom paper, caption anchoring, CSV import."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_tile_generator.captions.csv_io import (
    CaptionCSVError,
    lookup,
    read_caption_csv,
    write_caption_csv,
)
from pdf_tile_generator.models.settings import (
    PAPER_AUTO,
    PAPER_CUSTOM,
    CaptionSettings,
    LayoutSettings,
    OutputSettings,
    PageSettings,
    ProjectSettings,
)
from pdf_tile_generator.pdf.generator import PDFGenerator, TileJob
from pdf_tile_generator.pdf.layout import compute_page_tiles, effective_page_size


class TestCustomPaper:
    def test_custom_size_used_verbatim(self) -> None:
        page = PageSettings(paper_size=PAPER_CUSTOM, custom_width=1000.0, custom_height=500.0)
        size = effective_page_size(page, LayoutSettings(), CaptionSettings())
        assert size == (1000.0, 500.0)

    def test_custom_size_clamped_to_minimum(self) -> None:
        page = PageSettings(paper_size=PAPER_CUSTOM, custom_width=1.0, custom_height=1.0)
        assert page.page_size == (72.0, 72.0)

    def test_named_sizes_unchanged(self) -> None:
        page = PageSettings(paper_size="A4")
        size = effective_page_size(page, LayoutSettings(), CaptionSettings())
        assert size == page.page_size

    def test_custom_round_trips(self) -> None:
        settings = ProjectSettings(
            page=PageSettings(paper_size=PAPER_CUSTOM, custom_width=720.0, custom_height=720.0)
        )
        restored = ProjectSettings.from_dict(settings.to_dict())
        assert restored.page.custom_width == 720.0


class TestAutoPaper:
    def test_page_grows_with_grid(self) -> None:
        caption = CaptionSettings()
        small = effective_page_size(
            PageSettings(paper_size=PAPER_AUTO), LayoutSettings(rows=2, columns=2), caption
        )
        large = effective_page_size(
            PageSettings(paper_size=PAPER_AUTO), LayoutSettings(rows=6, columns=6), caption
        )
        assert large[0] > small[0]
        assert large[1] > small[1]

    def test_tiles_keep_requested_size(self) -> None:
        page = PageSettings(paper_size=PAPER_AUTO, auto_tile_width=200.0)
        tiles = compute_page_tiles(page, LayoutSettings(rows=4, columns=5), CaptionSettings())
        assert len(tiles) == 20
        assert tiles[0].width == pytest.approx(200.0)
        # Regardless of grid size, tile width must not shrink.
        tiles_big = compute_page_tiles(
            page, LayoutSettings(rows=8, columns=10), CaptionSettings()
        )
        assert tiles_big[0].width == pytest.approx(200.0)

    def test_auto_paper_with_images_per_page(self) -> None:
        page = PageSettings(paper_size=PAPER_AUTO)
        layout = LayoutSettings(auto_layout=True, images_per_page=10)
        tiles = compute_page_tiles(page, layout, CaptionSettings())
        assert len(tiles) >= 10

    def test_generates_valid_pdf(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "auto.pdf"
        settings = ProjectSettings(
            page=PageSettings(paper_size=PAPER_AUTO),
            layout=LayoutSettings(rows=1, columns=5),
            output=OutputSettings(output_path=str(output)),
        )
        jobs = [TileJob(path=str(p), caption=p.stem) for p in sample_images]
        result = PDFGenerator(settings).generate(jobs)
        assert result.page_count == 1
        assert output.read_bytes().startswith(b"%PDF-")


class TestDescriptions:
    def test_block_height_includes_description(self) -> None:
        without = CaptionSettings(description_enabled=False).block_height()
        with_desc = CaptionSettings(description_enabled=True).block_height()
        assert with_desc > without

    def test_pdf_with_descriptions(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "desc.pdf"
        settings = ProjectSettings(output=OutputSettings(output_path=str(output)))
        jobs = [
            TileJob(path=str(p), caption=p.stem, description=f"Description for {p.stem}")
            for p in sample_images
        ]
        result = PDFGenerator(settings).generate(jobs)
        assert result.image_count == len(sample_images)
        assert output.read_bytes().startswith(b"%PDF-")

    def test_description_without_caption(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "only_desc.pdf"
        settings = ProjectSettings(output=OutputSettings(output_path=str(output)))
        jobs = [TileJob(path=str(sample_images[0]), caption="", description="Only text")]
        assert PDFGenerator(settings).generate(jobs).image_count == 1


class TestCaptionCSV:
    def test_round_trip(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "captions.csv"
        write_caption_csv(
            csv_path,
            [
                (r"C:\photos\living_room.jpg", "Living Room", "Bright and airy"),
                ("/home/x/kitchen.png", "Kitchen", ""),
            ],
        )
        rows = read_caption_csv(csv_path)
        entry = lookup(rows, "/other/folder/LIVING_ROOM.JPG")
        assert entry is not None
        assert entry.caption == "Living Room"
        assert entry.description == "Bright and airy"

    def test_empty_cells_mean_unchanged(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "c.csv"
        csv_path.write_text("filename,caption,description\na.jpg,,New desc\n", encoding="utf-8")
        entry = lookup(read_caption_csv(csv_path), "a.jpg")
        assert entry is not None
        assert entry.caption is None
        assert entry.description == "New desc"

    def test_caption_only_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "c.csv"
        csv_path.write_text("filename,caption\na.jpg,Hello\n", encoding="utf-8")
        entry = lookup(read_caption_csv(csv_path), "a.jpg")
        assert entry is not None
        assert entry.caption == "Hello"
        assert entry.description is None

    def test_missing_filename_column_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("name,caption\na.jpg,X\n", encoding="utf-8")
        with pytest.raises(CaptionCSVError, match="filename"):
            read_caption_csv(csv_path)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CaptionCSVError):
            read_caption_csv(tmp_path / "nope.csv")

    def test_unmatched_lookup_returns_none(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "c.csv"
        csv_path.write_text("filename,caption\na.jpg,X\n", encoding="utf-8")
        assert lookup(read_caption_csv(csv_path), "other.jpg") is None

    def test_excel_bom_handled(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bom.csv"
        csv_path.write_bytes(b"\xef\xbb\xbffilename,caption\na.jpg,From Excel\n")
        entry = lookup(read_caption_csv(csv_path), "a.jpg")
        assert entry is not None
        assert entry.caption == "From Excel"
