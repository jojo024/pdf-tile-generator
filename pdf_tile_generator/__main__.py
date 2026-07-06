"""Allow ``python -m pdf_tile_generator``."""

import sys

from pdf_tile_generator.app.main import main

if __name__ == "__main__":
    sys.exit(main())
