"""Thumbnail generation for the image list (Pillow-only, no Qt dependency)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pdf_tile_generator.images.loader import open_image_safely

THUMBNAIL_SIZE = 96


def make_thumbnail(path: str | Path, size: int = THUMBNAIL_SIZE) -> Image.Image:
    """Create a thumbnail no larger than ``size`` x ``size`` pixels.

    Uses Pillow's ``draft`` mode so large JPEGs are decoded at reduced
    resolution instead of full size, keeping memory usage low.

    Raises:
        ImageLoadError: if the image cannot be opened.
    """
    image = open_image_safely(path, draft_size=(size, size))
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image
