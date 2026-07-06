"""Pure layout geometry: grid computation and tile placement.

All coordinates are in PDF points with the origin at the *bottom-left* of the
page (ReportLab convention). This module has no Qt or ReportLab dependency so
it can be unit-tested in isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pdf_tile_generator.models.settings import CaptionSettings, LayoutSettings, PageSettings


@dataclass(frozen=True)
class TileRect:
    """One tile on a page: the image area plus its caption area beneath.

    ``x``/``y`` locate the bottom-left corner of the whole tile.
    """

    x: float
    y: float
    width: float
    height: float
    image_height: float  # top portion of the tile reserved for the image
    caption_height: float  # bottom portion reserved for the caption block

    @property
    def image_y(self) -> float:
        """Bottom edge of the image area."""
        return self.y + self.caption_height

    @property
    def caption_top(self) -> float:
        """Top edge of the caption block (baseline math starts here)."""
        return self.y + self.caption_height


class LayoutError(ValueError):
    """Raised when settings produce an impossible layout (e.g. tiles too small)."""


def grid_for_count(images_per_page: int, page_width: float, page_height: float) -> tuple[int, int]:
    """Choose a (rows, columns) grid for ``images_per_page`` images.

    Picks the grid with the fewest wasted cells whose cell aspect ratio best
    matches the page aspect ratio, so tiles come out roughly square-ish.
    """
    count = max(1, images_per_page)
    best: tuple[float, float, int, int] | None = None
    for columns in range(1, count + 1):
        rows = math.ceil(count / columns)
        wasted = rows * columns - count
        cell_aspect = (page_width / columns) / (page_height / rows)
        # Prefer cells close to square (aspect ratio 1), then fewer wasted cells.
        score = (wasted, abs(math.log(cell_aspect)))
        if best is None or score < (best[0], best[1]):
            best = (score[0], score[1], rows, columns)
    assert best is not None
    return (best[2], best[3])


def compute_page_tiles(
    page: PageSettings,
    layout: LayoutSettings,
    caption: CaptionSettings,
) -> list[TileRect]:
    """Compute the tile rectangles for one page, in reading order.

    Reading order is left-to-right, top-to-bottom (the first tile returned is
    the top-left one).

    Raises:
        LayoutError: if margins/spacing leave no room for tiles, or the
            caption block is taller than the tile itself.
    """
    page_width, page_height = page.page_size
    rows, columns = layout.effective_grid(page_width, page_height)

    usable_width = page_width - 2 * page.margin - (columns - 1) * page.spacing_x
    usable_height = page_height - 2 * page.margin - (rows - 1) * page.spacing_y
    if usable_width <= 0 or usable_height <= 0:
        raise LayoutError(
            "Margins and spacing are larger than the page. Reduce margins or spacing."
        )

    tile_width = usable_width / columns
    tile_height = usable_height / rows
    caption_height = caption.block_height() + page.caption_spacing
    image_height = tile_height - caption_height
    if image_height < 8.0:
        raise LayoutError(
            "Tiles are too small for the caption text. Use fewer rows, smaller "
            "captions, or a larger paper size."
        )
    if tile_width < 8.0:
        raise LayoutError("Tiles are too narrow. Use fewer columns or smaller margins.")

    tiles: list[TileRect] = []
    for row in range(rows):
        # Row 0 is the top row; convert to bottom-left origin.
        top = page_height - page.margin - row * (tile_height + page.spacing_y)
        y = top - tile_height
        for column in range(columns):
            x = page.margin + column * (tile_width + page.spacing_x)
            tiles.append(
                TileRect(
                    x=x,
                    y=y,
                    width=tile_width,
                    height=tile_height,
                    image_height=image_height,
                    caption_height=caption_height,
                )
            )
    return tiles


def page_count(total_images: int, tiles_per_page: int) -> int:
    """Number of pages needed for ``total_images`` images."""
    if total_images <= 0 or tiles_per_page <= 0:
        return 0
    return math.ceil(total_images / tiles_per_page)


def fit_dimensions(
    source_width: float,
    source_height: float,
    box_width: float,
    box_height: float,
) -> tuple[float, float]:
    """Scale (source_width, source_height) to fit inside the box, keeping aspect."""
    if source_width <= 0 or source_height <= 0:
        return (0.0, 0.0)
    scale = min(box_width / source_width, box_height / source_height)
    return (source_width * scale, source_height * scale)
