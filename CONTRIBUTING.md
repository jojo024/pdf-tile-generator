# Contributing

Thanks for your interest in improving PDF Tile Generator!

## Getting started

1. Fork and clone the repository
2. `python -m venv .venv` and activate it
3. `pip install -e .[dev]`
4. `python -m pytest tests` — everything should pass before you start

## Making changes

- Create a feature branch from `main`
- Keep the core rule: **no Qt imports outside `pdf_tile_generator/gui/` and
  `app/`**. Caption/layout/PDF/image logic must stay headless and tested.
- Add or update tests for any behavior change; run the full suite
- Format and lint before committing:

```bash
black pdf_tile_generator tests
ruff check pdf_tile_generator tests
```

## Pull requests

- One logical change per PR
- Describe *what* and *why*; link related issues
- Include screenshots for UI changes
- New user-facing strings should be written for non-technical users
  (error messages are shown verbatim in dialogs)

## Reporting bugs

Open an issue with:
- OS and app version (Help → About)
- Steps to reproduce
- What you expected vs. what happened
- For generation problems: paper size, grid, and roughly how many images

## Code of conduct

Be kind. Assume good intent. Review the code, not the person.
