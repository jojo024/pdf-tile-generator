"""Manual update checking against GitHub releases.

This is the only code in the application that touches the network, and it
runs exclusively when the user clicks "Check for Updates" in the About
dialog. Nothing is downloaded or installed automatically.
"""

from pdf_tile_generator.update.checker import (
    ReleaseInfo,
    UpdateCheckError,
    check_for_update,
    is_newer_version,
    parse_version,
)

__all__ = [
    "ReleaseInfo",
    "UpdateCheckError",
    "check_for_update",
    "is_newer_version",
    "parse_version",
]
