# Build a Windows release with PyInstaller.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pyinstaller
if (-not $?) { throw "pyinstaller install failed" }

python -m pytest tests
if (-not $?) { throw "tests failed - not building" }

pyinstaller pdf_tile_generator.spec --noconfirm
if (-not $?) { throw "pyinstaller failed" }

Write-Host ""
Write-Host "Build complete: dist\PDFTileGenerator\PDFTileGenerator.exe"
