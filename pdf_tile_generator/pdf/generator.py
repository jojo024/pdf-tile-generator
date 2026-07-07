"""PDF generation with ReportLab.

The generator is GUI-agnostic: it reports progress through a callback and can
be cancelled via a ``threading.Event``, so the Qt layer can run it on a worker
thread without this module importing Qt.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from pdf_tile_generator.images.loader import ImageLoadError, open_image_safely
from pdf_tile_generator.models.settings import (
    CAPTION_FONTS,
    ImageFitMode,
    ProjectSettings,
    TextAlignment,
)
from pdf_tile_generator.pdf.layout import (
    TileRect,
    compute_page_tiles,
    effective_page_size,
    fit_dimensions,
)

logger = logging.getLogger(__name__)

#: progress callback: (images_done, images_total) -> None
ProgressCallback = Callable[[int, int], None]


class PDFGenerationError(Exception):
    """A user-presentable PDF generation failure."""


class PDFGenerationCancelled(Exception):
    """Raised internally when the cancel event is set."""


@dataclass
class TileJob:
    """One image to place in the PDF, with its caption and description text."""

    path: str
    caption: str
    description: str = ""


@dataclass
class GenerationResult:
    """Summary of a completed generation run."""

    output_path: str
    page_count: int
    image_count: int
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)


def _validate_output_path(output_path: str) -> Path:
    """Resolve and validate the output path; raise PDFGenerationError if unusable."""
    if not output_path or not output_path.strip():
        raise PDFGenerationError("No output file selected.")
    path = Path(output_path).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        raise PDFGenerationError(f"Invalid output path: {output_path}") from exc
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    if not path.parent.is_dir():
        raise PDFGenerationError(f"Output folder does not exist: {path.parent}")
    if path.is_dir():
        raise PDFGenerationError(f"Output path is a folder, not a file: {path}")
    return path


def _prepare_image(
    path: str,
    box_width_pt: float,
    box_height_pt: float,
    fit_mode: ImageFitMode,
    max_render_dpi: int,
) -> Image.Image:
    """Load an image and scale/crop it for a tile box measured in points.

    Very large images are downscaled so their effective resolution does not
    exceed ``max_render_dpi`` for the box they occupy - this bounds both the
    memory used during generation and the final PDF size, with no visible
    quality loss when printed.
    """
    # Target pixel budget for this box at the configured DPI.
    target_w_px = max(1, int(box_width_pt / 72.0 * max_render_dpi))
    target_h_px = max(1, int(box_height_pt / 72.0 * max_render_dpi))

    image = open_image_safely(path, draft_size=(target_w_px * 2, target_h_px * 2))

    if fit_mode is ImageFitMode.CROP:
        # Center-crop to exactly the box aspect ratio at the pixel budget.
        crop_w = min(target_w_px, image.width)
        box_aspect = box_width_pt / box_height_pt
        crop_h = max(1, int(crop_w / box_aspect))
        image = ImageOps.fit(
            image, (crop_w, crop_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
    elif image.width > target_w_px or image.height > target_h_px:
        image.thumbnail((target_w_px, target_h_px), Image.Resampling.LANCZOS)

    return image


def _wrap_caption(
    text: str, font_name: str, font_size: float, max_width: float, max_lines: int, wrap: bool
) -> list[str]:
    """Wrap caption text to fit ``max_width`` points, at most ``max_lines`` lines.

    Overflow is truncated with an ellipsis. Single words wider than the tile
    are hard-truncated character by character.
    """

    def truncate(line: str) -> str:
        ellipsis = "…"
        while line and stringWidth(line + ellipsis, font_name, font_size) > max_width:
            line = line[:-1]
        return (line + ellipsis) if line else ellipsis

    if not text:
        return []
    max_lines = max(1, max_lines) if wrap else 1

    # Greedy word wrap, ignoring the line limit for now.
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Enforce the line limit: merge any overflow into the last visible line,
    # then hard-truncate lines that are still too wide (oversized single words).
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]
    return [
        line if stringWidth(line, font_name, font_size) <= max_width else truncate(line)
        for line in lines
    ]


class PDFGenerator:
    """Renders a list of :class:`TileJob` items into a paginated PDF."""

    def __init__(self, settings: ProjectSettings) -> None:
        self._settings = settings

    def generate(
        self,
        jobs: list[TileJob],
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> GenerationResult:
        """Generate the PDF described by the settings and jobs.

        Args:
            jobs: Images and captions, in page order.
            progress: Called after each image with (done, total).
            cancel_event: When set, generation stops and the partial output
                file is removed.

        Raises:
            PDFGenerationError: for layout problems, write failures, or when
                no image could be rendered at all.
            PDFGenerationCancelled: if ``cancel_event`` was set.
        """
        if not jobs:
            raise PDFGenerationError("No images to generate. Add some images first.")

        settings = self._settings
        output_path = _validate_output_path(settings.output.output_path)
        tiles = compute_page_tiles(settings.page, settings.layout, settings.caption)
        per_page = len(tiles)
        font_name = CAPTION_FONTS.get(settings.caption.font, "Helvetica")
        try:
            caption_color = HexColor(settings.caption.color)
        except ValueError:
            caption_color = HexColor("#000000")

        total = len(jobs)
        skipped: list[tuple[str, str]] = []
        pages = 0

        page_size = effective_page_size(settings.page, settings.layout, settings.caption)
        try:
            canvas = Canvas(str(output_path), pagesize=page_size)
        except OSError as exc:
            raise PDFGenerationError(
                f"Cannot write to {output_path}. Check the folder exists and you "
                "have permission to write there."
            ) from exc

        try:
            canvas.setTitle(output_path.stem)
            drawn_any = False
            for index, job in enumerate(jobs):
                if cancel_event is not None and cancel_event.is_set():
                    raise PDFGenerationCancelled()
                tile = tiles[index % per_page]
                if index > 0 and index % per_page == 0:
                    canvas.showPage()
                    pages += 1
                try:
                    self._draw_tile(canvas, tile, job, font_name, caption_color)
                    drawn_any = True
                except ImageLoadError as exc:
                    logger.warning("Skipping %s: %s", job.path, exc)
                    skipped.append((job.path, str(exc)))
                    self._draw_placeholder(canvas, tile, job, font_name)
                if progress is not None:
                    progress(index + 1, total)
            canvas.showPage()
            pages += 1
            if not drawn_any:
                raise PDFGenerationError(
                    "None of the images could be read. The PDF was not created."
                )
            try:
                canvas.save()
            except OSError as exc:
                raise PDFGenerationError(
                    f"Failed to write the PDF (disk full or file locked?): {output_path}"
                ) from exc
        except (PDFGenerationCancelled, PDFGenerationError):
            self._cleanup_partial(output_path)
            raise
        except MemoryError as exc:
            self._cleanup_partial(output_path)
            raise PDFGenerationError(
                "Ran out of memory while generating. Try a lower image quality "
                "(max DPI) setting or fewer images per page."
            ) from exc

        logger.info("Generated %s (%d pages, %d images)", output_path, pages, total)
        return GenerationResult(
            output_path=str(output_path),
            page_count=pages,
            image_count=total - len(skipped),
            skipped=skipped,
        )

    def _draw_tile(
        self,
        canvas: Canvas,
        tile: TileRect,
        job: TileJob,
        font_name: str,
        caption_color: HexColor,
    ) -> None:
        """Draw one image and its caption into a tile."""
        settings = self._settings
        padding = settings.image.tile_padding
        box_w = max(1.0, tile.width - 2 * padding)
        box_h = max(1.0, tile.image_height - 2 * padding)

        image = _prepare_image(
            job.path, box_w, box_h, settings.image.fit_mode, settings.image.max_render_dpi
        )
        try:
            if settings.image.fit_mode is ImageFitMode.CROP:
                draw_w, draw_h = box_w, box_h
            else:
                draw_w, draw_h = fit_dimensions(image.width, image.height, box_w, box_h)
            x = tile.x + padding + (box_w - draw_w) / 2
            y = tile.image_y + padding + (box_h - draw_h) / 2
            reader = ImageReader(image)
            canvas.drawImage(
                reader, x, y, width=draw_w, height=draw_h, preserveAspectRatio=False, mask="auto"
            )
        finally:
            image.close()

        # Anchor the text to the image's real bottom edge, not the tile cell:
        # a wide (e.g. 16:9) image centered in a taller cell would otherwise
        # leave a confusing gap between the picture and its caption.
        self._draw_caption(canvas, tile, job, font_name, caption_color, anchor_top=y)

    def _draw_placeholder(
        self, canvas: Canvas, tile: TileRect, job: TileJob, font_name: str
    ) -> None:
        """Draw a bordered placeholder for an image that failed to load."""
        padding = self._settings.image.tile_padding
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#bbbbbb"))
        canvas.setFillColor(HexColor("#888888"))
        canvas.rect(
            tile.x + padding,
            tile.image_y + padding,
            tile.width - 2 * padding,
            tile.image_height - 2 * padding,
            stroke=1,
            fill=0,
        )
        canvas.setFont(font_name, 8)
        canvas.drawCentredString(
            tile.x + tile.width / 2,
            tile.image_y + tile.image_height / 2,
            "(image unavailable)",
        )
        canvas.restoreState()
        self._draw_caption(
            canvas,
            tile,
            job,
            font_name,
            HexColor("#888888"),
            anchor_top=tile.image_y + padding,
        )

    def _draw_caption(
        self,
        canvas: Canvas,
        tile: TileRect,
        job: TileJob,
        font_name: str,
        color: HexColor,
        anchor_top: float,
    ) -> None:
        """Draw the caption (and description) starting just below ``anchor_top``.

        ``anchor_top`` is the y coordinate of the drawn image's bottom edge, so
        the text always hugs the actual picture regardless of how much empty
        space the tile cell has around it.
        """
        settings = self._settings.caption
        if not job.caption and not job.description:
            return
        max_width = tile.width - 2 * self._settings.image.tile_padding

        def draw_lines(lines: list[str], font_size: float, baseline: float) -> float:
            canvas.setFont(font_name, font_size)
            for line in lines:
                if settings.alignment is TextAlignment.CENTER:
                    canvas.drawCentredString(tile.x + tile.width / 2, baseline, line)
                elif settings.alignment is TextAlignment.RIGHT:
                    right_edge = tile.x + tile.width - self._settings.image.tile_padding
                    canvas.drawRightString(right_edge, baseline, line)
                else:
                    canvas.drawString(tile.x + self._settings.image.tile_padding, baseline, line)
                baseline -= font_size * 1.25
            return baseline

        canvas.saveState()
        canvas.setFillColor(color)
        # "text_top" is where the next text block starts, walking downward.
        text_top = anchor_top - self._settings.page.caption_spacing
        if job.caption:
            lines = _wrap_caption(
                job.caption,
                font_name,
                settings.font_size,
                max_width,
                settings.max_lines,
                settings.wrap_text,
            )
            next_baseline = draw_lines(lines, settings.font_size, text_top - settings.font_size)
            last_baseline = next_baseline + settings.line_height
            text_top = last_baseline - settings.font_size * 0.25 - 2.0
        if settings.description_enabled and job.description:
            lines = _wrap_caption(
                job.description,
                font_name,
                settings.description_font_size,
                max_width,
                settings.description_max_lines,
                settings.wrap_text,
            )
            draw_lines(
                lines, settings.description_font_size, text_top - settings.description_font_size
            )
        canvas.restoreState()

    @staticmethod
    def _cleanup_partial(output_path: Path) -> None:
        """Best-effort removal of a partial output file after cancel/failure."""
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove partial file %s", output_path)
