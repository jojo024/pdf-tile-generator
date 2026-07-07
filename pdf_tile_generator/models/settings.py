"""Settings dataclasses shared by the GUI and the PDF generator.

All dimensional values are stored in PDF points (1 point = 1/72 inch) so the
generator can use them directly. Every settings class serializes to and from a
plain ``dict`` so the GUI can persist them with ``QSettings`` without the
model layer depending on Qt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, StrEnum
from typing import Any

#: Paper sizes in points (width, height) in portrait orientation.
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.2756, 841.8898),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (841.8898, 1190.5512),
}

#: Sentinel paper-size names that are not fixed sheets.
PAPER_CUSTOM = "Custom"
PAPER_AUTO = "Auto (fit grid)"

#: Fonts available for captions (ReportLab built-in Type 1 families;
#: no embedding required, render identically on every platform).
CAPTION_FONTS: dict[str, str] = {
    "Helvetica": "Helvetica",
    "Helvetica Bold": "Helvetica-Bold",
    "Times": "Times-Roman",
    "Times Bold": "Times-Bold",
    "Courier": "Courier",
}


class ImageFitMode(StrEnum):
    """How an image is placed inside its tile."""

    FIT = "fit"  # scale to fit entirely inside the tile (letterbox)
    CROP = "crop"  # scale and center-crop to fill the tile completely


class TextAlignment(StrEnum):
    """Horizontal caption alignment."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass
class PageSettings:
    """Paper size, orientation, and page-level spacing.

    ``paper_size`` may be a named sheet (A4, Letter, …), :data:`PAPER_CUSTOM`
    (use ``custom_width``/``custom_height``), or :data:`PAPER_AUTO` (the page
    grows to fit the grid at ``auto_tile_width`` × ``auto_tile_image_height``
    per tile — use :func:`pdf_tile_generator.pdf.layout.effective_page_size`
    to resolve the final dimensions).
    """

    paper_size: str = "A4"
    landscape: bool = False
    margin: float = 36.0  # points (0.5 inch)
    spacing_x: float = 12.0  # horizontal gap between tiles
    spacing_y: float = 12.0  # vertical gap between tiles
    caption_spacing: float = 4.0  # gap between image and caption
    custom_width: float = 595.2756  # points; used when paper_size == PAPER_CUSTOM
    custom_height: float = 841.8898
    auto_tile_width: float = 226.77  # 80 mm; used when paper_size == PAPER_AUTO
    auto_tile_image_height: float = 170.08  # 60 mm image area per tile

    @property
    def page_size(self) -> tuple[float, float]:
        """Fixed page (width, height) in points, honoring orientation.

        For :data:`PAPER_AUTO` this returns a nominal A4 fallback — callers
        that support auto sizing must use ``layout.effective_page_size``.
        """
        if self.paper_size == PAPER_CUSTOM:
            width = max(72.0, self.custom_width)
            height = max(72.0, self.custom_height)
            return (width, height)  # orientation is implicit in the numbers
        width, height = PAPER_SIZES.get(self.paper_size, PAPER_SIZES["A4"])
        if self.landscape:
            return (height, width)
        return (width, height)


@dataclass
class LayoutSettings:
    """Grid layout: explicit rows/columns or automatic from images per page."""

    auto_layout: bool = False
    rows: int = 3
    columns: int = 2
    images_per_page: int = 6  # used when auto_layout is True

    def effective_grid(self, page_width: float, page_height: float) -> tuple[int, int]:
        """Return the (rows, columns) actually used for the given page size."""
        if self.auto_layout:
            from pdf_tile_generator.pdf.layout import grid_for_count

            return grid_for_count(self.images_per_page, page_width, page_height)
        return (max(1, self.rows), max(1, self.columns))


@dataclass
class ImageSettings:
    """How images are rendered inside tiles."""

    fit_mode: ImageFitMode = ImageFitMode.FIT
    tile_padding: float = 4.0  # points of padding inside each tile
    max_render_dpi: int = 300  # cap for downscaling very large images


@dataclass
class CaptionSettings:
    """Caption (and optional description) text appearance.

    The description is a free-text second block rendered beneath the caption
    in a smaller size; its text comes from the per-image Description column
    in the image list (editable by hand or via CSV import).
    """

    font: str = "Helvetica"
    font_size: float = 10.0
    alignment: TextAlignment = TextAlignment.CENTER
    color: str = "#000000"  # hex RGB
    max_lines: int = 2
    wrap_text: bool = True
    title_case: bool = True
    description_enabled: bool = True
    description_font_size: float = 8.0
    description_max_lines: int = 2

    @property
    def line_height(self) -> float:
        """Vertical space for one line of caption text, in points."""
        return self.font_size * 1.25

    @property
    def description_line_height(self) -> float:
        """Vertical space for one line of description text, in points."""
        return self.description_font_size * 1.25

    def block_height(self) -> float:
        """Total vertical space reserved for the caption + description block."""
        height = self.line_height * max(1, self.max_lines)
        if self.description_enabled:
            height += 2.0 + self.description_line_height * max(1, self.description_max_lines)
        return height


@dataclass
class OutputSettings:
    """Where the PDF is written and post-generation behavior."""

    output_path: str = ""
    open_after_generation: bool = True


@dataclass
class ProjectSettings:
    """Aggregate of all settings; one object describes a full generation job."""

    page: PageSettings = field(default_factory=PageSettings)
    layout: LayoutSettings = field(default_factory=LayoutSettings)
    image: ImageSettings = field(default_factory=ImageSettings)
    caption: CaptionSettings = field(default_factory=CaptionSettings)
    output: OutputSettings = field(default_factory=OutputSettings)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (enums become their string values)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectSettings:
        """Deserialize, ignoring unknown keys and falling back to defaults."""

        def load(dataclass_type: type, values: Any) -> Any:
            defaults = dataclass_type()
            if not isinstance(values, dict):
                return defaults
            valid = {f: getattr(defaults, f) for f in defaults.__dataclass_fields__}
            for key, value in values.items():
                if key not in valid:
                    continue
                current = getattr(defaults, key)
                try:
                    if isinstance(current, Enum):
                        value = type(current)(value)
                    elif isinstance(current, bool):
                        value = bool(value)
                    elif isinstance(current, int) and not isinstance(current, bool):
                        value = int(value)
                    elif isinstance(current, float):
                        value = float(value)
                    elif isinstance(current, str):
                        value = str(value)
                    setattr(defaults, key, value)
                except (ValueError, TypeError):
                    continue  # keep the default for malformed values
            return defaults

        data = data if isinstance(data, dict) else {}
        return cls(
            page=load(PageSettings, data.get("page")),
            layout=load(LayoutSettings, data.get("layout")),
            image=load(ImageSettings, data.get("image")),
            caption=load(CaptionSettings, data.get("caption")),
            output=load(OutputSettings, data.get("output")),
        )
