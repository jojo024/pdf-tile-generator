"""Safe image loading.

All image decoding in the application funnels through :func:`open_image_safely`
so corrupt files, decompression bombs, and unsupported formats are handled in
exactly one place and always surface as :class:`ImageLoadError`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

#: File extensions the application accepts (lowercase, with dot).
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
)

#: Refuse to decode images larger than this many pixels (decompression bombs).
MAX_PIXELS = 250_000_000

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageLoadError(Exception):
    """A user-presentable image loading failure."""


def is_supported_image(path: str | Path) -> bool:
    """Return True if the path has a supported image extension."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def open_image_safely(
    path: str | Path, draft_size: tuple[int, int] | None = None
) -> Image.Image:
    """Open an image, apply EXIF orientation, and return an RGB(A) Pillow image.

    Args:
        path: The image file to open.
        draft_size: Optional (width, height) hint. When given, JPEG/derived
            formats are decoded at reduced resolution (Pillow ``draft`` mode),
            which drastically lowers memory use for thumbnails and previews.

    Raises:
        ImageLoadError: with a user-friendly message for any failure mode
            (missing file, permission denied, corrupt data, unsupported format,
            decompression bomb).
    """
    file_path = Path(path)
    if not is_supported_image(file_path):
        raise ImageLoadError(f"Unsupported image format: {file_path.name}")
    if not file_path.is_file():
        raise ImageLoadError(f"File not found: {file_path}")
    try:
        image = Image.open(file_path)
        if draft_size is not None:
            image.draft("RGB", draft_size)
        image.load()  # force decode now so corruption surfaces here
    except UnidentifiedImageError as exc:
        raise ImageLoadError(f"Not a valid image file: {file_path.name}") from exc
    except Image.DecompressionBombError as exc:
        raise ImageLoadError(f"Image is too large to open safely: {file_path.name}") from exc
    except PermissionError as exc:
        raise ImageLoadError(f"Permission denied reading: {file_path.name}") from exc
    except OSError as exc:
        raise ImageLoadError(f"Could not read image (corrupt file?): {file_path.name}") from exc

    try:
        image = ImageOps.exif_transpose(image)
    except Exception:  # noqa: BLE001 - malformed EXIF must never be fatal
        logger.warning("Ignoring malformed EXIF data in %s", file_path)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    return image
