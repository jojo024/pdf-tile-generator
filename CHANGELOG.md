# Changelog

## 1.1.0 — 2026-07-07

### Added
- **Auto (fit grid) paper size**: the page grows to fit the grid at your
  chosen tile size, so large grids are no longer squeezed into A4.
- **Custom paper size**: enter exact page width/height in millimeters.
- **Description column** in the image list, rendered under each caption in a
  smaller font (size and line limit configurable, can be disabled).
- **CSV import/export** for bulk captions and descriptions
  (`filename,caption,description`; matched by filename, Excel BOM tolerated).

### Changed
- Captions (and descriptions) now sit directly beneath the **actual image**,
  not the bottom of the tile cell — wide images no longer have their caption
  floating far below the picture.

### Fixed
- Caption generation from Windows-style paths (`C:\photos\img.jpg`) now works
  identically on macOS/Linux (was CI-failing on POSIX runners).

## 1.0.0 — 2026-07-06

Initial release: grid layout, page/caption/image settings, live preview,
background generation with cancel, manual update check, PyInstaller packaging.
