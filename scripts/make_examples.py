"""Generate the example images and example PDF shipped in ``examples/``.

Run from the repository root:

    python scripts/make_examples.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from pdf_tile_generator.captions import generate_caption
from pdf_tile_generator.models.settings import OutputSettings, ProjectSettings
from pdf_tile_generator.pdf.generator import PDFGenerator, TileJob

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "examples" / "images"
OUTPUT_PDF = ROOT / "examples" / "example_contact_sheet.pdf"

SPECS: list[tuple[str, tuple[int, int], tuple[int, int, int]]] = [
    ("living_room_01.jpg", (800, 600), (183, 110, 90)),
    ("living_room_02.jpg", (800, 600), (160, 120, 100)),
    ("kitchen-window.jpg", (600, 800), (90, 140, 160)),
    ("IMG_1234.jpg", (800, 600), (100, 150, 110)),
    ("IMG-3452.png", (640, 640), (140, 100, 160)),
    ("master_bedroom.jpg", (800, 500), (170, 150, 110)),
    ("my-dog sleeping.jpg", (700, 700), (120, 110, 100)),
    ("garden_view_north.jpg", (900, 600), (100, 160, 120)),
    ("bathroom_2.jpg", (500, 750), (150, 160, 170)),
    ("hallway.jpg", (600, 900), (130, 120, 140)),
]


def make_placeholder(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    """Draw a pleasant gradient placeholder with simple geometry."""
    width, height = size
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    # Vertical gradient toward a lighter tint.
    for y in range(height):
        factor = y / height * 0.45
        row_color = tuple(min(255, int(channel + (255 - channel) * factor)) for channel in color)
        draw.line([(0, y), (width, y)], fill=row_color)
    # A few translucent circles for texture.
    for index in range(3):
        radius = min(size) // (3 + index)
        cx = int(width * (0.25 + 0.25 * index))
        cy = int(height * (0.3 + 0.2 * math.sin(index * 2.1)))
        tint = tuple(min(255, channel + 25 + index * 10) for channel in color)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius], outline=tint, width=6
        )
    image.save(path)


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    jobs: list[TileJob] = []
    for name, size, color in SPECS:
        path = IMAGES_DIR / name
        if not path.exists():
            make_placeholder(path, size, color)
        jobs.append(TileJob(path=str(path), caption=generate_caption(name)))
        print(f"  {name:28s} -> {generate_caption(name)}")

    settings = ProjectSettings(output=OutputSettings(output_path=str(OUTPUT_PDF)))
    result = PDFGenerator(settings).generate(jobs)
    print(f"\nWrote {result.output_path}: {result.image_count} images, {result.page_count} pages")


if __name__ == "__main__":
    main()
