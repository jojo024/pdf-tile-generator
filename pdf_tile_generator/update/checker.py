"""Query the GitHub Releases API for a newer version.

Design constraints (see the project security notes):
    * Only runs when the user explicitly asks (no background polling).
    * One HTTPS GET to api.github.com; nothing else is contacted.
    * Never downloads or executes anything - on success the caller gets the
      release's web page URL to open in the browser.
    * All failures surface as :class:`UpdateCheckError` with a message safe
      to show end users.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from pdf_tile_generator import __version__

logger = logging.getLogger(__name__)

GITHUB_OWNER = "jojo024"
GITHUB_REPO = "pdf-tile-generator"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 1_000_000  # the release JSON is a few KB; cap defensively


class UpdateCheckError(Exception):
    """A user-presentable update check failure."""


@dataclass(frozen=True)
class ReleaseInfo:
    """The newest published release."""

    version: str  # e.g. "1.2.0" (tag with the leading "v" stripped)
    url: str  # human-facing release page to open in a browser


def parse_version(text: str) -> tuple[int, ...]:
    """Extract a comparable numeric tuple from a version string or tag.

    ``"v1.2.3"`` → ``(1, 2, 3)``; non-numeric suffixes are ignored
    (``"1.2.0-beta"`` → ``(1, 2, 0)``). Unparseable input gives ``()``.
    """
    numbers = re.findall(r"\d+", text.split("-")[0] if "-" in text else text)
    return tuple(int(n) for n in numbers)


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    """True if ``candidate`` is strictly newer than ``current``."""
    candidate_tuple = parse_version(candidate)
    current_tuple = parse_version(current)
    if not candidate_tuple or not current_tuple:
        return False
    return candidate_tuple > current_tuple


def _parse_release(data: object) -> ReleaseInfo:
    """Extract :class:`ReleaseInfo` from a GitHub API release payload."""
    if not isinstance(data, dict):
        raise UpdateCheckError("Unexpected response from the update server.")
    tag = data.get("tag_name")
    url = data.get("html_url") or RELEASES_PAGE_URL
    if not isinstance(tag, str) or not tag:
        raise UpdateCheckError("Unexpected response from the update server.")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        url = RELEASES_PAGE_URL
    return ReleaseInfo(version=tag.lstrip("vV"), url=url)


def check_for_update(current_version: str = __version__) -> ReleaseInfo | None:
    """Return the newest release if it is newer than ``current_version``.

    Returns ``None`` when the application is up to date.

    Raises:
        UpdateCheckError: if the network is unavailable, the request times
            out, or the response cannot be understood.
    """
    request = urllib.request.Request(
        _API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"pdf-tile-generator/{current_version}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = response.read(_MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # No releases published yet - treat as "up to date".
            return None
        logger.warning("Update check HTTP error: %s", exc)
        raise UpdateCheckError(
            "The update server could not be reached. Please try again later."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.info("Update check failed (offline?): %s", exc)
        raise UpdateCheckError(
            "Could not check for updates. Are you connected to the internet?"
        ) from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UpdateCheckError("Unexpected response from the update server.") from exc

    release = _parse_release(data)
    if is_newer_version(release.version, current_version):
        return release
    return None
