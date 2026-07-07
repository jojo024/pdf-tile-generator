"""Generate human-friendly captions from image filenames.

Rules:
    * Remove the file extension.
    * Replace underscores and hyphens with spaces.
    * Collapse runs of whitespace into a single space.
    * Preserve numbers.
    * With smart capitalization (default): capitalize all-lowercase words while
      preserving words that already contain capitals (``IMG``, ``iPhone``).

Examples:
    ``living_room_01.jpg``  -> ``Living Room 01``
    ``IMG-3452.PNG``        -> ``IMG 3452``
    ``my-dog sleeping.jpeg`` -> ``My Dog Sleeping``
"""

from __future__ import annotations

import re
from pathlib import PurePath

_SEPARATORS = re.compile(r"[_\-]+")
_WHITESPACE = re.compile(r"\s+")


def _capitalize_word(word: str) -> str:
    """Capitalize a word only if it contains no uppercase letters already.

    Words such as ``IMG`` or ``iPhone`` are preserved verbatim; purely numeric
    words are returned unchanged.
    """
    if any(character.isupper() for character in word):
        return word
    return word[:1].upper() + word[1:]


def generate_caption(filename: str | PurePath, title_case: bool = True) -> str:
    """Generate a display caption from an image filename or path.

    Args:
        filename: A filename or full path; only the final component is used.
        title_case: When ``True`` (default), apply smart capitalization so
            ``living_room`` becomes ``Living Room`` while ``IMG`` stays ``IMG``.
            When ``False``, the original word casing is kept as-is.

    Returns:
        The generated caption. May be an empty string for degenerate names
        such as ``.jpg``.
    """
    # Take the basename treating both / and \ as separators, so Windows-style
    # paths caption identically on every platform (PurePath alone would keep
    # "C:\photos\" as part of the stem on POSIX).
    basename = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    stem = PurePath(basename).stem
    if stem.startswith("."):
        # Names like ".jpg" are pure extensions (dotfile semantics); no base name.
        stem = ""
    text = _SEPARATORS.sub(" ", stem)
    text = _WHITESPACE.sub(" ", text).strip()
    if not text:
        return ""
    if title_case:
        text = " ".join(_capitalize_word(word) for word in text.split(" "))
    return text
