"""End-to-end tests for PDF generation (no GUI required)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from pdf_tile_generator.captions import generate_caption
from pdf_tile_generator.models.settings import (
    ImageFitMode,
    ImageSettings,
    LayoutSettings,
    OutputSettings,
    ProjectSettings,
)
from pdf_tile_generator.pdf.generator import (
    PDFGenerationCancelled,
    PDFGenerationError,
    PDFGenerator,
    TileJob,
    _wrap_caption,
)


def make_jobs(paths: list[Path]) -> list[TileJob]:
    return [TileJob(path=str(p), caption=generate_caption(p)) for p in paths]


def make_settings(output: Path, **overrides) -> ProjectSettings:
    settings = ProjectSettings(**overrides)
    settings.output = OutputSettings(output_path=str(output))
    return settings


def assert_valid_pdf(path: Path) -> None:
    data = path.read_bytes()
    assert data.startswith(b"%PDF-"), "missing PDF header"
    assert b"%%EOF" in data[-1024:], "missing PDF trailer"


class TestGeneration:
    def test_basic_generation(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        result = PDFGenerator(make_settings(output)).generate(make_jobs(sample_images))
        assert Path(result.output_path) == output.resolve()
        assert result.image_count == len(sample_images)
        assert result.skipped == []
        assert result.page_count == 1  # 5 images, 6 tiles per page
        assert_valid_pdf(output)

    def test_pagination(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        settings = make_settings(output, layout=LayoutSettings(rows=2, columns=1))
        jobs = make_jobs(sample_images)  # 5 images, 2 per page -> 3 pages
        result = PDFGenerator(settings).generate(jobs)
        assert result.page_count == 3
        assert_valid_pdf(output)

    def test_crop_mode(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        settings = make_settings(output, image=ImageSettings(fit_mode=ImageFitMode.CROP))
        result = PDFGenerator(settings).generate(make_jobs(sample_images))
        assert result.image_count == len(sample_images)
        assert_valid_pdf(output)

    def test_progress_reported(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        calls: list[tuple[int, int]] = []
        PDFGenerator(make_settings(output)).generate(
            make_jobs(sample_images), progress=lambda d, t: calls.append((d, t))
        )
        assert calls == [(i + 1, len(sample_images)) for i in range(len(sample_images))]

    def test_missing_extension_added(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "noext"
        result = PDFGenerator(make_settings(output)).generate(make_jobs(sample_images))
        assert result.output_path.endswith(".pdf")

    def test_auto_layout(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        settings = make_settings(
            output, layout=LayoutSettings(auto_layout=True, images_per_page=4)
        )
        result = PDFGenerator(settings).generate(make_jobs(sample_images))
        assert result.page_count == 2  # 5 images, 4 per page
        assert_valid_pdf(output)


class TestErrorHandling:
    def test_no_jobs_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PDFGenerationError, match="No images"):
            PDFGenerator(make_settings(tmp_path / "out.pdf")).generate([])

    def test_no_output_path_raises(self, sample_images: list[Path]) -> None:
        settings = ProjectSettings()
        with pytest.raises(PDFGenerationError, match="No output file"):
            PDFGenerator(settings).generate(make_jobs(sample_images))

    def test_missing_folder_raises(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "does" / "not" / "exist" / "out.pdf"
        with pytest.raises(PDFGenerationError, match="folder does not exist"):
            PDFGenerator(make_settings(output)).generate(make_jobs(sample_images))

    def test_corrupt_image_skipped_not_fatal(
        self, sample_images: list[Path], corrupt_image: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.pdf"
        jobs = make_jobs([*sample_images, corrupt_image])
        result = PDFGenerator(make_settings(output)).generate(jobs)
        assert result.image_count == len(sample_images)
        assert len(result.skipped) == 1
        assert str(corrupt_image) == result.skipped[0][0]
        assert_valid_pdf(output)

    def test_all_corrupt_raises_and_removes_file(
        self, corrupt_image: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.pdf"
        with pytest.raises(PDFGenerationError, match="None of the images"):
            PDFGenerator(make_settings(output)).generate(make_jobs([corrupt_image]))
        assert not output.exists()

    def test_cancellation(self, sample_images: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "out.pdf"
        cancel = threading.Event()
        cancel.set()
        with pytest.raises(PDFGenerationCancelled):
            PDFGenerator(make_settings(output)).generate(
                make_jobs(sample_images), cancel_event=cancel
            )
        assert not output.exists(), "partial file must be cleaned up"

    def test_impossible_layout_raises(self, sample_images: list[Path], tmp_path: Path) -> None:
        from pdf_tile_generator.models.settings import PageSettings
        from pdf_tile_generator.pdf.layout import LayoutError

        settings = make_settings(tmp_path / "out.pdf", page=PageSettings(margin=400.0))
        with pytest.raises(LayoutError):
            PDFGenerator(settings).generate(make_jobs(sample_images))


class TestCaptionWrapping:
    FONT = "Helvetica"

    def test_short_caption_single_line(self) -> None:
        assert _wrap_caption("Hello", self.FONT, 10, 200, 2, True) == ["Hello"]

    def test_empty_caption(self) -> None:
        assert _wrap_caption("", self.FONT, 10, 200, 2, True) == []

    def test_wraps_to_two_lines(self) -> None:
        lines = _wrap_caption("Living Room With Very Nice Windows", self.FONT, 10, 90, 3, True)
        assert 2 <= len(lines) <= 3
        assert lines[0].startswith("Living")

    def test_respects_max_lines_with_ellipsis(self) -> None:
        text = "An Extremely Long Caption That Cannot Possibly Fit On Two Small Lines At All"
        lines = _wrap_caption(text, self.FONT, 10, 80, 2, True)
        assert len(lines) == 2
        assert lines[-1].endswith("…")

    def test_no_wrap_gives_one_line(self) -> None:
        lines = _wrap_caption("Some Very Long Caption Here", self.FONT, 10, 60, 3, False)
        assert len(lines) == 1

    def test_giant_word_truncated(self) -> None:
        lines = _wrap_caption("Supercalifragilisticexpialidocious", self.FONT, 10, 50, 2, True)
        assert len(lines) == 1
        assert lines[0].endswith("…")

    def test_500_images_layout_is_fast(self, tmp_path: Path) -> None:
        # Regression guard: layout math must not slow down with image count.
        import time

        from pdf_tile_generator.models.settings import CaptionSettings, PageSettings
        from pdf_tile_generator.pdf.layout import compute_page_tiles, page_count

        start = time.perf_counter()
        tiles = compute_page_tiles(PageSettings(), LayoutSettings(), CaptionSettings())
        pages = page_count(500, len(tiles))
        elapsed = time.perf_counter() - start
        assert pages == 84
        assert elapsed < 0.1
