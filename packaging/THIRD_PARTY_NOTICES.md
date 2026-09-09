# Third-party notices

The packaged IC2V desktop application includes software distributed under
separate licenses:

- **FFmpeg**, supplied by the pinned `imageio-ffmpeg` package used for the
  release build. FFmpeg license and source information:
  <https://ffmpeg.org/legal.html> and <https://ffmpeg.org/download.html>.
- **imageio-ffmpeg**, used to provision the packaged FFmpeg executable:
  <https://github.com/imageio/imageio-ffmpeg>.
- **Qt for Python / PySide6**, used by the desktop interface:
  <https://www.qt.io/qt-licensing>.

Release engineering must retain the license files installed by these packages,
record the exact package versions, and review the selected FFmpeg binary's
configuration before public distribution. In particular, codec selection can
change the obligations that apply to the binary.
