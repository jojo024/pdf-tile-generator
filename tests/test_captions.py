"""Tests for caption generation."""

from __future__ import annotations

import pytest

from pdf_tile_generator.captions import generate_caption


class TestSpecExamples:
    """The three examples given in the specification."""

    def test_living_room(self) -> None:
        assert generate_caption("living_room_01.jpg") == "Living Room 01"

    def test_img_number_preserves_caps(self) -> None:
        assert generate_caption("IMG-3452.PNG") == "IMG 3452"

    def test_mixed_separators(self) -> None:
        assert generate_caption("my-dog sleeping.jpeg") == "My Dog Sleeping"


class TestRules:
    def test_extension_removed(self) -> None:
        assert generate_caption("photo.jpg") == "Photo"

    def test_underscores_become_spaces(self) -> None:
        assert generate_caption("a_b_c.png") == "A B C"

    def test_hyphens_become_spaces(self) -> None:
        assert generate_caption("a-b-c.png") == "A B C"

    def test_multiple_separators_collapse(self) -> None:
        assert generate_caption("a__--__b.png") == "A B"

    def test_multiple_spaces_collapse(self) -> None:
        assert generate_caption("a   b.png") == "A B"

    def test_numbers_preserved(self) -> None:
        assert generate_caption("room_101.jpg") == "Room 101"

    def test_mixed_case_word_preserved(self) -> None:
        assert generate_caption("my_iPhone_pic.jpg") == "My iPhone Pic"

    def test_title_case_off_preserves_original(self) -> None:
        assert generate_caption("living_room.jpg", title_case=False) == "living room"

    def test_title_case_off_still_replaces_separators(self) -> None:
        assert generate_caption("IMG-3452.PNG", title_case=False) == "IMG 3452"

    def test_full_path_uses_basename(self) -> None:
        assert generate_caption(r"C:\photos\living_room.jpg") == "Living Room"
        assert generate_caption("/home/user/living_room.jpg") == "Living Room"


class TestEdgeCases:
    @pytest.mark.parametrize("name", ["", ".jpg", "___.png", "-.gif"])
    def test_degenerate_names_give_empty_caption(self, name: str) -> None:
        assert generate_caption(name) == ""

    def test_leading_trailing_separators_stripped(self) -> None:
        assert generate_caption("_photo_.jpg") == "Photo"

    def test_only_numbers(self) -> None:
        assert generate_caption("12345.jpg") == "12345"

    def test_unicode_preserved(self) -> None:
        assert generate_caption("café_menu.jpg") == "Café Menu"

    def test_double_extension_only_last_removed(self) -> None:
        assert generate_caption("archive.backup.jpg") == "Archive.backup"
