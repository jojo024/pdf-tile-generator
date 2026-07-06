"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def sample_images(tmp_path: Path) -> list[Path]:
    """Create a handful of small real images in a temp directory."""
    paths = []
    specs = [
        ("living_room_01.jpg", "JPEG", (320, 240), (200, 60, 60)),
        ("IMG-3452.png", "PNG", (240, 320), (60, 200, 60)),
        ("my-dog sleeping.webp", "WEBP", (300, 300), (60, 60, 200)),
        ("kitchen.bmp", "BMP", (160, 120), (200, 200, 60)),
        ("hallway_2.tiff", "TIFF", (120, 160), (200, 60, 200)),
    ]
    for name, fmt, size, color in specs:
        path = tmp_path / name
        Image.new("RGB", size, color).save(path, fmt)
        paths.append(path)
    return paths


@pytest.fixture
def corrupt_image(tmp_path: Path) -> Path:
    """A file with an image extension but garbage contents."""
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"this is definitely not a JPEG")
    return path
