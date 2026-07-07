# PyInstaller spec file for PDF Tile Generator.
# Build with:  pyinstaller pdf_tile_generator.spec
# Produces a windowed (no console) one-folder build in dist/PDFTileGenerator.

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("reportlab.pdfbase")

a = Analysis(
    ["pdf_tile_generator/app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    excludes=[
        # Trim unused Qt modules to shrink the build.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="PDFTileGenerator",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no terminal window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PDFTileGenerator",
)

# macOS app bundle (ignored on other platforms).
app = BUNDLE(
    coll,
    name="PDF Tile Generator.app",
    bundle_identifier="org.pdftilegenerator.app",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "1.2.0",
    },
)
