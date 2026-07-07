"""Velopack-based in-place updates.

This wraps the ``velopack`` SDK so the rest of the app never imports it
directly. Everything degrades gracefully: when the app is running from source,
from the portable zip, or on a build where the native ``velopack`` binary is
unavailable, :meth:`VelopackUpdater.is_available` returns ``False`` and the
GUI falls back to the manual "open the download page" flow in
:mod:`pdf_tile_generator.update.checker`.

Only installed builds (produced by ``vpk pack`` and installed via the Velopack
Setup.exe) can self-update, because only those have the local Velopack
manifest and ``Update.exe`` helper that performs the file swap on restart.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: The GitHub repository whose Releases feed provides Velopack update packages.
REPO_URL = "https://github.com/jojo024/pdf-tile-generator"

try:  # The native extension may be missing in some environments.
    import velopack

    _IMPORTED = True
except Exception as exc:  # noqa: BLE001 - any import failure means "no updates here"
    velopack = None  # type: ignore[assignment]
    _IMPORTED = False
    logger.info("velopack SDK not available: %s", exc)


def run_startup_hook() -> None:
    """Run Velopack's startup logic; must be called before any UI is created.

    In an installed build this handles the post-install/update hooks (and may
    exit or restart the process). When not launched by Velopack, or when the
    SDK is unavailable, it is a harmless no-op.
    """
    if not _IMPORTED:
        return
    try:
        velopack.App().run()
    except Exception:  # noqa: BLE001 - the hook must never block startup
        logger.exception("Velopack startup hook failed; continuing without it")


@dataclass(frozen=True)
class PendingUpdate:
    """A newer release discovered by :meth:`VelopackUpdater.check`."""

    version: str
    #: Opaque velopack ``UpdateInfo`` passed back to download/apply.
    info: object


class VelopackUpdater:
    """Checks for, downloads, and applies updates via Velopack + GitHub.

    All methods that touch the network or disk may block and should be called
    from a worker thread. Construction is cheap and never raises.
    """

    def __init__(self, repo_url: str = REPO_URL) -> None:
        self._repo_url = repo_url
        self._manager: object | None = None
        self._resolved = False  # whether we have tried to build the manager

    def is_available(self) -> bool:
        """True if this build can self-update (installed via Velopack)."""
        return self._manager_or_none() is not None

    def current_version(self) -> str | None:
        """The installed version per Velopack, or ``None`` if not applicable."""
        manager = self._manager_or_none()
        if manager is None:
            return None
        try:
            return manager.get_current_version()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return None

    def check(self) -> PendingUpdate | None:
        """Return a :class:`PendingUpdate` if a newer release exists, else None.

        Raises:
            UpdateUnavailableError: if this build cannot self-update.
            VelopackError: if the check fails (network/feed problems).
        """
        manager = self._require_manager()
        try:
            info = manager.check_for_updates()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise VelopackError(_friendly_error(exc)) from exc
        if info is None:
            return None
        return PendingUpdate(version=info.TargetFullRelease.Version, info=info)

    def download(
        self, update: PendingUpdate, progress: Callable[[int], None] | None = None
    ) -> None:
        """Download the update package (delta when possible).

        Args:
            update: The pending update from :meth:`check`.
            progress: Optional callback receiving a 0-100 completion percentage.

        Raises:
            VelopackError: if the download fails.
        """
        manager = self._require_manager()
        try:
            manager.download_updates(update.info, progress)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise VelopackError(_friendly_error(exc)) from exc

    def apply_and_restart(self, update: PendingUpdate) -> None:
        """Apply the downloaded update and restart the app. Does not return.

        Raises:
            VelopackError: if applying fails before the restart occurs.
        """
        manager = self._require_manager()
        try:
            manager.apply_updates_and_restart(update.info)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise VelopackError(_friendly_error(exc)) from exc

    # ------------------------------------------------------------------ internal

    def _manager_or_none(self) -> object | None:
        if not self._resolved:
            self._resolved = True
            self._manager = self._build_manager()
        return self._manager

    def _build_manager(self) -> object | None:
        if not _IMPORTED:
            return None
        try:
            source = velopack.GithubSource(self._repo_url, None, False)
            manager = velopack.UpdateManager(source)
            # Reading the current version only succeeds inside a Velopack
            # install; it raises for source/portable runs.
            manager.get_current_version()
            return manager
        except Exception as exc:  # noqa: BLE001
            logger.info("Velopack self-update not available in this build: %s", exc)
            return None

    def _require_manager(self) -> object:
        manager = self._manager_or_none()
        if manager is None:
            raise UpdateUnavailableError(
                "Automatic updates are only available in the installed version."
            )
        return manager


class VelopackError(Exception):
    """A user-presentable Velopack update failure."""


class UpdateUnavailableError(VelopackError):
    """Raised when the current build cannot self-update."""


def _friendly_error(exc: Exception) -> str:
    """Map a raw Velopack/network exception to a user-facing message."""
    text = str(exc).lower()
    if "network" in text or "connection" in text or "resolve" in text or "timed" in text:
        return "Could not reach the update server. Check your internet connection."
    return "The update could not be completed. Please try again later."
