#!/usr/bin/env bash
# Build a macOS/Linux release with PyInstaller.
# Usage:  ./scripts/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pip install --upgrade pyinstaller
python -m pytest tests
pyinstaller pdf_tile_generator.spec --noconfirm

echo
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Build complete: dist/PDF Tile Generator.app"
else
    echo "Build complete: dist/PDFTileGenerator/PDFTileGenerator"
fi
