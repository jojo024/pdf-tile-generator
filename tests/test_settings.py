"""Tests for settings serialization round-trips."""

from __future__ import annotations

from pdf_tile_generator.models.settings import (
    CaptionSettings,
    ImageFitMode,
    LayoutSettings,
    PageSettings,
    ProjectSettings,
    TextAlignment,
)


class TestRoundTrip:
    def test_defaults_round_trip(self) -> None:
        settings = ProjectSettings()
        assert ProjectSettings.from_dict(settings.to_dict()) == settings

    def test_customized_round_trip(self) -> None:
        settings = ProjectSettings(
            page=PageSettings(paper_size="Letter", landscape=True, margin=20.0),
            layout=LayoutSettings(auto_layout=True, images_per_page=9),
            caption=CaptionSettings(
                font="Courier",
                alignment=TextAlignment.RIGHT,
                color="#ff0000",
                title_case=False,
            ),
        )
        restored = ProjectSettings.from_dict(settings.to_dict())
        assert restored == settings
        assert restored.caption.alignment is TextAlignment.RIGHT
        assert restored.image.fit_mode is ImageFitMode.FIT


class TestRobustness:
    def test_empty_dict_gives_defaults(self) -> None:
        assert ProjectSettings.from_dict({}) == ProjectSettings()

    def test_garbage_input_gives_defaults(self) -> None:
        assert ProjectSettings.from_dict({"page": "nonsense", "layout": 42}) == ProjectSettings()

    def test_unknown_keys_ignored(self) -> None:
        data = ProjectSettings().to_dict()
        data["page"]["evil_key"] = "boo"
        data["brand_new_section"] = {}
        assert ProjectSettings.from_dict(data) == ProjectSettings()

    def test_malformed_enum_falls_back(self) -> None:
        data = ProjectSettings().to_dict()
        data["caption"]["alignment"] = "diagonal"
        restored = ProjectSettings.from_dict(data)
        assert restored.caption.alignment is TextAlignment.CENTER

    def test_page_size_orientation(self) -> None:
        portrait = PageSettings(paper_size="A4", landscape=False).page_size
        landscape = PageSettings(paper_size="A4", landscape=True).page_size
        assert portrait[0] < portrait[1]
        assert landscape[0] > landscape[1]

    def test_unknown_paper_size_falls_back_to_a4(self) -> None:
        assert PageSettings(paper_size="Tabloid").page_size == PageSettings().page_size
