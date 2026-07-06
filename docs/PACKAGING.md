# Packaging Guide

Standalone builds use **PyInstaller** with the checked-in spec file
`pdf_tile_generator.spec` (one-folder, windowed, unused Qt modules excluded).

Always build **on the platform you are targeting** — PyInstaller does not
cross-compile.

## Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

Output: `dist\PDFTileGenerator\PDFTileGenerator.exe`. Zip the
`PDFTileGenerator` folder for distribution.

Notes:
- SmartScreen will warn on unsigned executables. For public distribution,
  sign with `signtool` and an Authenticode certificate.
- For an installer, point [Inno Setup](https://jrsoftware.org/isinfo.php) at
  the `dist\PDFTileGenerator` folder.

## macOS

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
./scripts/build.sh
```

Output: `dist/PDF Tile Generator.app` (the spec's `BUNDLE` step, with
`NSHighResolutionCapable` set for Retina displays).

Notes:
- Build on the oldest macOS you want to support.
- For distribution outside your machine: codesign and notarize
  (`codesign --deep --sign "Developer ID Application: …"`, then `notarytool`).
- Create a DMG with `hdiutil create -srcfolder "dist/PDF Tile Generator.app" …`.

## Linux

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
./scripts/build.sh
```

Output: `dist/PDFTileGenerator/PDFTileGenerator`. Tar the folder, or wrap it
in an AppImage with `appimagetool` for broad compatibility. Build on the
oldest glibc you want to support (e.g. an Ubuntu LTS container).

## What the build scripts do

1. Install/upgrade PyInstaller
2. Run the full test suite (**the build aborts if any test fails**)
3. Run PyInstaller with the spec file

## Spec file highlights

- `console=False` — no terminal window
- Excludes QtWebEngine/QtQml/QtQuick/QtMultimedia/QtNetwork and tkinter,
  which shrinks the bundle substantially
- `collect_submodules("reportlab.pdfbase")` — ReportLab font metrics are
  imported dynamically and would otherwise be missed

## Alternative: Briefcase

The codebase is Briefcase-compatible (single package, one entry point:
`pdf_tile_generator.app.main:main`). If you prefer native installers
(MSI/DMG/AppImage) over PyInstaller folders, add Briefcase's
`[tool.briefcase]` table to `pyproject.toml` following the
[BeeWare docs](https://briefcase.readthedocs.io/); no code changes needed.

## Release checklist

1. Bump `__version__` in `pdf_tile_generator/__init__.py` and `pyproject.toml`
2. `python -m pytest tests`
3. Build on each target platform
4. Launch the packaged app, add images, and generate a PDF (smoke test)
5. Tag and attach the archives
