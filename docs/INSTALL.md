# Installation Guide

## For users (standalone builds)

If you received a packaged release, no Python installation is needed. Download
from the [Releases page](https://github.com/jojo024/pdf-tile-generator/releases):

- **Windows (recommended)**: run `PdfTileGenerator-win-Setup.exe`. It installs
  per-user (no admin) and enables **in-app updates** — future versions download
  only what changed via Help → About → Check for Updates. SmartScreen may warn
  on the unsigned installer; choose "More info → Run anyway".
- **Windows (portable)**: unzip `PdfTileGenerator-win-Portable.zip` and run
  `PDFTileGenerator.exe`. No install; updates via the "open download page" flow.
- **macOS**: unzip and copy `PDF Tile Generator.app` to Applications.
  First launch may require right-click → Open (unsigned app).
- **Linux**: unpack and run `PDFTileGenerator/PDFTileGenerator`.

To create these builds yourself, see [PACKAGING.md](PACKAGING.md).

## For running from source

### Prerequisites

- Python **3.11 or newer** (3.11, 3.12, and 3.13 are tested)
- pip

### Steps

```bash
cd pdf_tile_generator
python -m venv .venv
```

Activate the virtual environment:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Windows (cmd): `.venv\Scripts\activate.bat`
- macOS/Linux: `source .venv/bin/activate`

Install and run:

```bash
pip install -e .
python -m pdf_tile_generator
```

The `pip install -e .` step installs the three runtime dependencies:

| Package | Purpose |
| --- | --- |
| PySide6 | Desktop UI (Qt 6) |
| ReportLab | PDF generation |
| Pillow | Image decoding, scaling, thumbnails |

### Linux notes

PySide6 needs the usual Qt runtime libraries. On minimal distributions:

```bash
# Debian/Ubuntu
sudo apt install libxcb-cursor0 libgl1 libegl1
```

### Verifying the installation

```bash
pip install -e .[dev]
python -m pytest tests
```

All tests should pass.
