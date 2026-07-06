"""Tests for the pure layout geometry."""

from __future__ import annotations

import pytest

from pdf_tile_generator.models.settings import (
    CaptionSettings,
    LayoutSettings,
    PageSettings,
)
from pdf_tile_generator.pdf.layout import (
    LayoutError,
    compute_page_tiles,
    fit_dimensions,
    grid_for_count,
    page_count,
)


def make_tiles(**overrides):
    page = overrides.pop("page", PageSettings())
    layout = overrides.pop("layout", LayoutSettings(rows=3, columns=2))
    caption = overrides.pop("caption", CaptionSettings())
    return compute_page_tiles(page, layout, caption)


class TestComputePageTiles:
    def test_tile_count_matches_grid(self) -> None:
        assert len(make_tiles(layout=LayoutSettings(rows=3, columns=2))) == 6
        assert len(make_tiles(layout=LayoutSettings(rows=4, columns=4))) == 16

    def test_tiles_inside_page(self) -> None:
        page = PageSettings()
        width, height = page.page_size
        for tile in make_tiles(page=page):
            assert tile.x >= page.margin - 1e-6
            assert tile.y >= page.margin - 1e-6
            assert tile.x + tile.width <= width - page.margin + 1e-6
            assert tile.y + tile.height <= height - page.margin + 1e-6

    def test_no_overlap(self) -> None:
        tiles = make_tiles(layout=LayoutSettings(rows=3, columns=3))
        for i, a in enumerate(tiles):
            for b in tiles[i + 1 :]:
                x_disjoint = a.x + a.width <= b.x + 1e-6 or b.x + b.width <= a.x + 1e-6
                y_disjoint = a.y + a.height <= b.y + 1e-6 or b.y + b.height <= a.y + 1e-6
                assert x_disjoint or y_disjoint, "tiles overlap"

    def test_reading_order_top_left_first(self) -> None:
        tiles = make_tiles(layout=LayoutSettings(rows=2, columns=2))
        assert tiles[0].y > tiles[2].y  # first row is above second
        assert tiles[0].x < tiles[1].x  # first column is left of second

    def test_caption_area_below_image(self) -> None:
        for tile in make_tiles():
            assert tile.image_y == pytest.approx(tile.y + tile.caption_height)
            assert tile.image_height + tile.caption_height == pytest.approx(tile.height)

    def test_landscape_swaps_dimensions(self) -> None:
        portrait = PageSettings(landscape=False)
        landscape = PageSettings(landscape=True)
        assert portrait.page_size == landscape.page_size[::-1]

    def test_huge_margin_raises_layout_error(self) -> None:
        with pytest.raises(LayoutError):
            make_tiles(page=PageSettings(margin=500.0))

    def test_too_many_rows_raises_layout_error(self) -> None:
        with pytest.raises(LayoutError):
            make_tiles(
                layout=LayoutSettings(rows=12, columns=1),
                caption=CaptionSettings(font_size=30, max_lines=5),
            )

    def test_auto_layout_produces_enough_tiles(self) -> None:
        layout = LayoutSettings(auto_layout=True, images_per_page=7)
        tiles = make_tiles(layout=layout)
        assert len(tiles) >= 7


class TestGridForCount:
    @pytest.mark.parametrize("count", [1, 2, 3, 4, 6, 9, 12, 20, 64])
    def test_grid_fits_count(self, count: int) -> None:
        rows, columns = grid_for_count(count, 595.0, 842.0)
        assert rows * columns >= count
        assert rows * columns - count < columns  # no fully-empty rows

    def test_single_image(self) -> None:
        assert grid_for_count(1, 595.0, 842.0) == (1, 1)

    def test_zero_clamped(self) -> None:
        assert grid_for_count(0, 595.0, 842.0) == (1, 1)


class TestPageCount:
    def test_exact_fit(self) -> None:
        assert page_count(12, 6) == 2

    def test_remainder_adds_page(self) -> None:
        assert page_count(13, 6) == 3

    def test_zero_images(self) -> None:
        assert page_count(0, 6) == 0

    def test_single_image(self) -> None:
        assert page_count(1, 6) == 1

    def test_500_images(self) -> None:
        assert page_count(500, 6) == 84


class TestFitDimensions:
    def test_wide_image_letterboxes(self) -> None:
        width, height = fit_dimensions(200, 100, 100, 100)
        assert (width, height) == (100, 50)

    def test_tall_image_pillarboxes(self) -> None:
        width, height = fit_dimensions(100, 200, 100, 100)
        assert (width, height) == (50, 100)

    def test_never_exceeds_box(self) -> None:
        width, height = fit_dimensions(3000, 2000, 150, 120)
        assert width <= 150 and height <= 120

    def test_degenerate_source(self) -> None:
        assert fit_dimensions(0, 0, 100, 100) == (0.0, 0.0)
