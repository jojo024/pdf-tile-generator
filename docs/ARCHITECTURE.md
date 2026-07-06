# Architecture

## Design principles

1. **Core logic is GUI-free.** Caption generation, layout geometry, image
   loading, and PDF generation have no Qt dependency. They are plain Python,
   fully unit-testable, and reusable (e.g. for a future CLI).
2. **One hardened image path.** Every image decode in the application goes
   through `images.loader.open_image_safely`, which handles missing files,
   permission errors, corrupt data, unsupported formats, and decompression
   bombs in a single place, raising one exception type (`ImageLoadError`).
3. **The UI thread never blocks.** Thumbnails load on the global
   `QThreadPool`; PDF generation runs on a dedicated `QThread` and reports
   progress via signals. Cancellation uses a `threading.Event` checked
   between images.
4. **Settings are data.** `ProjectSettings` is a tree of dataclasses that
   serializes to/from plain dicts, so persistence (QSettings + JSON) is
   trivial and tolerant of corrupt or outdated stored data.

## Module map

```
pdf_tile_generator/
├── app/main.py            Entry point: logging, QApplication, MainWindow
├── captions/
│   └── caption_generator.py   Pure function: filename → caption
├── models/
│   └── settings.py        Dataclasses: Page/Layout/Image/Caption/Output
│                          settings + dict (de)serialization; paper sizes,
│                          fonts. No Qt, no ReportLab.
├── pdf/
│   ├── layout.py          Pure geometry: grid selection, TileRect
│   │                      placement (bottom-left origin, points),
│   │                      page counting. Raises LayoutError.
│   └── generator.py       PDFGenerator: ReportLab canvas rendering,
│                          caption wrapping, image scaling/cropping,
│                          progress callback + cancel event, partial-file
│                          cleanup. Raises PDFGenerationError.
├── images/
│   ├── loader.py          open_image_safely (the hardened decode path),
│   │                      supported-extension checks, EXIF transpose.
│   └── thumbnail.py       Bounded-size thumbnails using Pillow draft mode.
├── update/
│   └── checker.py         Manual update check (stdlib urllib, one HTTPS GET
│                          to the GitHub Releases API, only on user click).
│                          The application's sole network access.
└── gui/
    ├── main_window.py     Assembles everything; generation workflow;
    │                      QSettings persistence (window state + settings).
    ├── image_list.py      Table of thumbnail/filename/caption; drag-drop,
    │                      reordering, editable captions.
    ├── settings_panel.py  Widget ↔ ProjectSettings bridge (mm ↔ points).
    ├── preview.py         Page-layout diagram + page count estimate.
    ├── workers.py         ThumbnailTask (QRunnable), PdfWorker (QThread).
    └── dialogs.py         Error/success/overwrite/About dialogs.
```

## Data flow for "Generate PDF"

```
MainWindow._start_generation
    ├─ SettingsPanel.settings()        → ProjectSettings (points)
    ├─ ImageListWidget.paths/captions  → list[TileJob]
    ├─ overwrite confirmation (dialogs.confirm_overwrite)
    └─ PdfWorker(settings, jobs).start()
           └─ PDFGenerator.generate()
                 ├─ _validate_output_path
                 ├─ layout.compute_page_tiles → list[TileRect]
                 └─ per image: _prepare_image → drawImage → _draw_caption
                    (progress signal after each; cancel event checked)
    signals: progressChanged / succeeded / failed / cancelled
```

## Coordinate systems and units

- The **model and PDF layers** work in PDF points (1/72 inch), bottom-left
  origin (ReportLab's convention). `TileRect` stores the whole tile plus the
  split between image area (top) and caption block (bottom).
- The **GUI** displays millimeters and converts at the settings-panel
  boundary (`settings_panel._mm/_pt`).
- The **preview** converts points → widget pixels, flipping the y-axis.

## Error-handling strategy

| Failure | Behavior |
| --- | --- |
| One image corrupt/missing | Skipped; placeholder drawn; listed in success dialog |
| All images unreadable | `PDFGenerationError`; no output file left behind |
| Impossible layout (margins too big, captions too tall) | `LayoutError` shown in preview *before* generating, and as a dialog if generation is attempted |
| Output folder missing / not writable / disk full | `PDFGenerationError` with a user-friendly message; partial file removed |
| Cancel pressed | Generation stops between images; partial file removed |
| Anything unexpected in a worker | Caught, logged with traceback, generic error dialog; app never crashes |

## Performance notes

- Thumbnails use Pillow **draft mode** so large JPEGs decode at reduced
  resolution; list rows appear immediately with a placeholder and fill in
  lazily as the thread pool completes.
- During generation, each image is downscaled to at most `max_render_dpi`
  (150/300/600) for the tile it occupies before embedding — memory stays
  bounded and PDFs stay small regardless of source image size (a 100 MP
  photo embeds at the same size as a 2 MP one for the same tile).
- Only one source image is fully decoded at a time during generation and it
  is closed immediately after being drawn.

## Extension points

- **New paper size**: add one entry to `models.settings.PAPER_SIZES`.
- **New caption font**: add to `models.settings.CAPTION_FONTS` (ReportLab
  base-14 names need no embedding; TTF embedding would go in `pdf/generator.py`).
- **CLI**: reuse `PDFGenerator` + `generate_caption` directly; nothing in
  `pdf/`, `captions/`, `images/`, `models/` imports Qt.
- **Project save/load**: `ProjectSettings.to_dict/from_dict` plus the image
  path list is the complete document model.
