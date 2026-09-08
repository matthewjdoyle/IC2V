# Build with: pyinstaller --noconfirm packaging/ic2v-gui.spec
from pathlib import Path

import imageio_ffmpeg
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


project = Path(SPECPATH).parent
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
icon = project / "build" / "ic2v.ico"
icon.parent.mkdir(parents=True, exist_ok=True)
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
QSvgRenderer(str(project / "src" / "ic2v" / "assets" / "ic2v.svg")).render(painter)
painter.end()
if not image.save(str(icon), "ICO"):
    raise RuntimeError("Could not generate the Windows application icon.")

a = Analysis(
    [str(project / "packaging" / "ic2v_gui.py")],
    pathex=[str(project / "src")],
    binaries=[(ffmpeg, ".")],
    datas=[(str(project / "src" / "ic2v" / "assets" / "ic2v.svg"), "ic2v/assets")],
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
