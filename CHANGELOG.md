# Changelog

## 1.3.1 — 2026-07-07

### Fixed
- Closing the About dialog while an update download is in progress no longer
  risks a late callback into the destroyed dialog; signals are detached and
  the download thread is awaited on close.

### Notes
- First release delivered as a **delta** to installed 1.3.0 users — the
  in-app updater downloads only the changed bytes.

## 1.3.0 — 2026-07-07

### Added
- **In-app updates (Windows)** via [Velopack](https://velopack.io). The
  Windows build now ships as a per-user installer (`Setup.exe`); once
  installed, **Help → About → Check for Updates** downloads only what changed
  (delta updates, typically 1–5 MB rather than the full ~55 MB) and installs
  on restart. No admin rights, no reinstall.
- A **portable Windows zip** is still provided for users who prefer not to
  install; it uses the manual "open download page" update flow.

### Notes
- macOS and Linux continue to ship as archives with the manual update flow.
- The update check remains **user-initiated only** — nothing is downloaded or
  installed in the background.

## 1.2.0 — 2026-07-07

### Added
- **Custom columns**: "Add Column…" creates additional per-image fields
  (e.g. Location, Client); each renders as another text line under the tile,
  below the description. Columns persist between sessions and can be removed
  with "Remove Column…".
- CSV import/export includes custom columns; unknown CSV headers
  automatically create matching columns on import.

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
