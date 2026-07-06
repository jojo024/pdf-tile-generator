"""Tests for the manual update checker (no network access in tests)."""

from __future__ import annotations

import pytest

from pdf_tile_generator.update import (
    UpdateCheckError,
    is_newer_version,
    parse_version,
)
from pdf_tile_generator.update.checker import RELEASES_PAGE_URL, _parse_release


class TestParseVersion:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1.0.0", (1, 0, 0)),
            ("v1.2.3", (1, 2, 3)),
            ("V2.0", (2, 0)),
            ("1.2.0-beta", (1, 2, 0)),
            ("10.20.30", (10, 20, 30)),
            ("nonsense", ()),
            ("", ()),
        ],
    )
    def test_parse(self, text: str, expected: tuple[int, ...]) -> None:
        assert parse_version(text) == expected


class TestIsNewerVersion:
    def test_newer(self) -> None:
        assert is_newer_version("1.1.0", "1.0.0")
        assert is_newer_version("2.0.0", "1.9.9")

    def test_equal_is_not_newer(self) -> None:
        assert not is_newer_version("1.0.0", "1.0.0")

    def test_older_is_not_newer(self) -> None:
        assert not is_newer_version("0.9.0", "1.0.0")

    def test_tag_prefix_handled(self) -> None:
        assert is_newer_version("v1.1.0", "1.0.0")

    def test_unparseable_is_never_newer(self) -> None:
        assert not is_newer_version("garbage", "1.0.0")
        assert not is_newer_version("1.1.0", "garbage")

    def test_defaults_to_app_version(self) -> None:
        assert is_newer_version("999.0.0")
        assert not is_newer_version("0.0.1")


class TestParseRelease:
    def test_valid_payload(self) -> None:
        release = _parse_release(
            {"tag_name": "v1.2.0", "html_url": "https://github.com/x/y/releases/tag/v1.2.0"}
        )
        assert release.version == "1.2.0"
        assert release.url.endswith("v1.2.0")

    def test_missing_tag_raises(self) -> None:
        with pytest.raises(UpdateCheckError):
            _parse_release({"html_url": "https://github.com/x"})

    def test_non_dict_raises(self) -> None:
        with pytest.raises(UpdateCheckError):
            _parse_release(["not", "a", "dict"])

    def test_non_github_url_replaced(self) -> None:
        release = _parse_release({"tag_name": "v9.9.9", "html_url": "https://evil.example/x"})
        assert release.url == RELEASES_PAGE_URL

    def test_missing_url_falls_back(self) -> None:
        release = _parse_release({"tag_name": "v1.0.1"})
        assert release.url == RELEASES_PAGE_URL
