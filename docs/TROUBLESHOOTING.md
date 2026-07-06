# Troubleshooting

## The app won't start

**`ModuleNotFoundError: No module named 'pdf_tile_generator'`**
Run `pip install -e .` from the repository root (with your virtualenv active),
then `python -m pdf_tile_generator`.

**Linux: `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`**
Install the Qt runtime dependencies:
`sudo apt install libxcb-cursor0 libgl1 libegl1`

**Windows: nothing happens when launching the packaged exe**
Launch it from a terminal to see the error. If it mentions a missing DLL,
install the latest Microsoft Visual C++ Redistributable.

## Images

**An image shows ⚠ instead of a thumbnail**
Hover the ⚠ for the reason. Common causes: the file is corrupt, truncated,
not actually an image despite its extension, or unreadable due to
permissions. Such images are skipped during generation (you'll get a list in
the completion dialog) — they never abort the PDF.

**A photo appears rotated**
The app honors EXIF orientation automatically. If a photo still looks wrong,
the file's EXIF data is incorrect; re-export it from a photo tool.

**"Image is too large to open safely"**
Files over 250 megapixels are rejected as potential decompression bombs.
Downscale the image first.

## Layout and PDF

**"Tiles are too small for the caption text" / red X in the preview**
The grid doesn't fit: reduce rows/columns, margins, caption size, or max
lines — or switch to a larger paper size / landscape. The preview updates
live, so adjust until the warning disappears.

**Captions are cut off with "…"**
Increase "Maximum lines", reduce the font size, or use fewer columns so
tiles are wider.

**"Cannot write to …" / "Output folder does not exist"**
Choose an output location you can write to via Output → Browse…. If the PDF
is open in a viewer (Windows locks open files), close it and regenerate.

**The PDF is huge**
Set Images → Quality to "Print (300 DPI)" or "Draft (150 DPI)". Quality
caps the resolution at which images are embedded.

**Generation is slow with hundreds of images**
Expected work scales with image count; the UI stays responsive and shows
progress. Draft quality is significantly faster. You can cancel at any time.

## Settings

**Reset all remembered settings**
Settings are stored with Qt's `QSettings` under organization
`PDFTileGenerator`:
- Windows: registry key `HKEY_CURRENT_USER\Software\PDFTileGenerator`
- macOS: `~/Library/Preferences/com.pdftilegenerator.*`
- Linux: `~/.config/PDFTileGenerator/`

Delete it and restart the app to return to defaults. Corrupt stored settings
are ignored automatically (defaults are used).
