"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from pdf_tile_generator import APP_NAME, ORG_NAME, __version__
from pdf_tile_generator.gui.main_window import MainWindow
from pdf_tile_generator.update import run_startup_hook


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    """Launch the application."""
    # Velopack's startup hook must run before any UI. It handles post-install
    # and post-update tasks in packaged builds and is a no-op otherwise. It may
    # restart the process during an update, so keep it first.
    run_startup_hook()

    _configure_logging()
    logging.getLogger(__name__).info("Starting %s %s", APP_NAME, __version__)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
