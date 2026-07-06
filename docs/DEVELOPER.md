# Developer Guide

## Setup

```bash
cd pdf_tile_generator
python -m venv .venv
# activate it, then:
pip install -e .[dev]
```

## Running

```bash
python -m pdf_tile_generator          # module form
pdf-tile-generator                    # installed GUI script
```

Logging goes to stderr at INFO level (configured in `app/main.py`).

## Testing

```bash
python -m pytest tests                # full suite
python -m pytest tests -k captions    # one area
python -m pytest tests --cov=pdf_tile_generator --cov-report=term-missing
```

The suite covers caption generation (including the three examples from the
specification), layout geometry (bounds, overlap, pagination, auto-grid),
settings round-trips and corrupt-data tolerance, safe image loading
(corrupt/truncated/missing/EXIF), thumbnails, and end-to-end PDF generation
(pagination, crop mode, progress, cancellation, partial-file cleanup).

Tests do not require a display: the GUI layer is intentionally excluded from
core logic. To smoke-test the GUI headless, set `QT_QPA_PLATFORM=offscreen`.

## Code style

- **Black** (line length 100): `black pdf_tile_generator tests`
- **Ruff**: `ruff check pdf_tile_generator tests`
- Type hints everywhere; dataclasses for value objects
- Google-style docstrings on public functions and classes
- Qt naming (camelCase overrides/signals) is confined to `gui/`

## Project conventions

- Model/PDF layers use **points**; GUI shows **millimeters**. Convert only in
  `gui/settings_panel.py`.
- Never call `PIL.Image.open` directly — use
  `images.loader.open_image_safely` so every decode gets the same hardening.
- Worker threads communicate with widgets **only through signals**.
- User-facing failures are typed exceptions with human-readable messages
  (`ImageLoadError`, `LayoutError`, `PDFGenerationError`); the GUI shows the
  message text directly, so write them for end users.

## Adding a feature (example: page numbers)

1. Add the option to `models/settings.py` (e.g. `PageSettings.page_numbers`).
   Serialization is automatic.
2. Render it in `pdf/generator.py` (draw after each `showPage` boundary).
3. Add the checkbox in `gui/settings_panel.py` (`_build_page_group`,
   `settings()`, `load()`).
4. Add tests in `tests/test_pdf_generator.py`.
