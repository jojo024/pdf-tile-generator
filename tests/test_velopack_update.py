"""Tests for the Velopack update wrapper.

These run in a plain (non-installed) environment, so they exercise the
graceful-degradation paths. The actual download/apply cycle needs a real
Velopack install and is verified manually against a published release.
"""

from __future__ import annotations

import pytest

from pdf_tile_generator.update import (
    UpdateUnavailableError,
    VelopackError,
    VelopackUpdater,
    run_startup_hook,
)
from pdf_tile_generator.update.velopack_update import _friendly_error


class TestStartupHook:
    def test_never_raises(self) -> None:
        # Safe to call whether or not the SDK/install context is present.
        run_startup_hook()


class TestUnavailableInSourceRun:
    def test_not_available(self) -> None:
        assert VelopackUpdater().is_available() is False

    def test_current_version_none(self) -> None:
        assert VelopackUpdater().current_version() is None

    def test_check_raises_unavailable(self) -> None:
        with pytest.raises(UpdateUnavailableError):
            VelopackUpdater().check()

    def test_download_raises_unavailable(self) -> None:
        from pdf_tile_generator.update import PendingUpdate

        with pytest.raises(UpdateUnavailableError):
            VelopackUpdater().download(PendingUpdate(version="9.9.9", info=object()))

    def test_apply_raises_unavailable(self) -> None:
        from pdf_tile_generator.update import PendingUpdate

        with pytest.raises(UpdateUnavailableError):
            VelopackUpdater().apply_and_restart(PendingUpdate(version="9.9.9", info=object()))

    def test_unavailable_is_a_velopack_error(self) -> None:
        # So the UI can catch a single base type.
        assert issubclass(UpdateUnavailableError, VelopackError)


class TestFriendlyError:
    def test_network_message(self) -> None:
        msg = _friendly_error(RuntimeError("network connection failed"))
        assert "internet" in msg.lower()

    def test_generic_message(self) -> None:
        msg = _friendly_error(RuntimeError("something odd"))
        assert "try again" in msg.lower()
