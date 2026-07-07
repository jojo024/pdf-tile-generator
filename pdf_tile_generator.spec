# PyInstaller spec file for PDF Tile Generator.
# Build with:  pyinstaller pdf_tile_generator.spec
# Produces a windowed (no console) one-folder build in dist/PDFTileGenerator.

from PyInstaller.utils.hooks import collect_all, collect_submodules

hiddenimports = collect_submodules("reportlab.pdfbase")

# velopack ships a native extension (.pyd) plus py.typed; collect_all grabs the
# binary and data files so the update SDK works in the packaged build.
velo_datas, velo_binaries, velo_hiddenimports = collect_all("velopack")
hiddenimports += velo_hiddenimports

a = Analysis(
    ["pdf_tile_generator/app/main.py"],
    pathex=["."],
    binaries=velo_binaries,
    datas=velo_datas,
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
        "CFBundleShortVersionString": "1.3.0",
    },
)
