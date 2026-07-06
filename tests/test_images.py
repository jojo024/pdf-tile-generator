"""Tests for safe image loading and thumbnails."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pdf_tile_generator.images.loader import (
    ImageLoadError,
    is_supported_image,
    open_image_safely,
)
from pdf_tile_generator.images.thumbnail import make_thumbnail


class TestIsSupportedImage:
    @pytest.mark.parametrize(
        "name", ["a.jpg", "a.JPEG", "a.png", "a.BMP", "a.tif", "a.tiff", "a.webp"]
    )
    def test_supported(self, name: str) -> None:
        assert is_supported_image(name)

    @pytest.mark.parametrize("name", ["a.gif", "a.pdf", "a.txt", "a.exe", "a", "a.jpg.exe"])
    def test_unsupported(self, name: str) -> None:
        assert not is_supported_image(name)


class TestOpenImageSafely:
    def test_opens_all_sample_formats(self, sample_images: list[Path]) -> None:
        for path in sample_images:
            image = open_image_safely(path)
            assert image.mode in ("RGB", "RGBA")
            assert image.width > 0

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ImageLoadError, match="not found"):
            open_image_safely(tmp_path / "nope.jpg")

    def test_corrupt_file(self, corrupt_image: Path) -> None:
        with pytest.raises(ImageLoadError, match="valid image"):
            open_image_safely(corrupt_image)

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("hello")
        with pytest.raises(ImageLoadError, match="Unsupported"):
            open_image_safely(path)

    def test_truncated_image(self, tmp_path: Path) -> None:
        # A real JPEG header followed by truncation.
        source = tmp_path / "good.jpg"
        Image.new("RGB", (400, 400), (10, 20, 30)).save(source, "JPEG")
        data = source.read_bytes()
        truncated = tmp_path / "truncated.jpg"
        truncated.write_bytes(data[: len(data) // 3])
        with pytest.raises(ImageLoadError):
            open_image_safely(truncated)

    def test_exif_orientation_applied(self, tmp_path: Path) -> None:
        from PIL import Image as PILImage

        path = tmp_path / "rotated.jpg"
        image = PILImage.new("RGB", (200, 100), (1, 2, 3))
        exif = image.getexif()
        exif[0x0112] = 6  # rotate 90 CW
        image.save(path, "JPEG", exif=exif)
        loaded = open_image_safely(path)
        assert (loaded.width, loaded.height) == (100, 200)


class TestMakeThumbnail:
    def test_thumbnail_size_bounded(self, sample_images: list[Path]) -> None:
        for path in sample_images:
            thumb = make_thumbnail(path, size=96)
            assert max(thumb.width, thumb.height) <= 96

    def test_thumbnail_keeps_aspect(self, sample_images: list[Path]) -> None:
        thumb = make_thumbnail(sample_images[0], size=96)  # 320x240 source
        assert thumb.width / thumb.height == pytest.approx(320 / 240, rel=0.05)

    def test_thumbnail_corrupt_raises(self, corrupt_image: Path) -> None:
        with pytest.raises(ImageLoadError):
            make_thumbnail(corrupt_image)
