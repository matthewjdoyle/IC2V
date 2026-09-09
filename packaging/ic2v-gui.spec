# Build with: pyinstaller --noconfirm packaging/ic2v-gui.spec
import sys
from pathlib import Path

import imageio_ffmpeg

project = Path(SPECPATH).parent
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
icon_ext = "icns" if sys.platform == "darwin" else "ico"
icon = project / "src" / "ic2v" / "assets" / f"ic2v.{icon_ext}"

a = Analysis(
    [str(project / "packaging" / "ic2v_gui.py")],
    pathex=[str(project / "src")],
    binaries=[(ffmpeg, ".")],
    datas=[
        (str(project / "src" / "ic2v" / "assets" / "ic2v.svg"), "ic2v/assets"),
        (str(icon), "ic2v/assets"),
    ],
    hiddenimports=[],
    excludes=["imageio_ffmpeg"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IC2V",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="IC2V",
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='IC2V.app',
        icon=str(icon),
        bundle_identifier=None,
    )

