"""
Runs FFmpeg conversions and publishes collision-safe output files.

Author: M J Doyle
"""

from collections.abc import Callable
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import uuid

from .collection import ConversionError, discover, inspect, prepare


ENCODERS = {"mp4": "libx264", "mov": "libx264", "webm": "libvpx-vp9", "gif": "gif"}


def resolve_ffmpeg(explicit: str | None) -> str:
    executable = shutil.which(explicit or "ffmpeg")
    if executable is None:
        raise ConversionError("FFmpeg was not found. Install FFmpeg and add it to PATH, "
                              "or supply --ffmpeg PATH. See the README for setup instructions.")
    return executable


def run_ffmpeg(arguments: list[str]) -> str:
    # communicate() drains stderr while FFmpeg runs; cancellation must reap the child
    # before temporary files can be removed, particularly on Windows.
    try:
        process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ConversionError(f"Could not start FFmpeg: {exc}") from exc
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        process.kill()
        process.communicate()
        raise
    if process.returncode:
        detail = stderr.strip()[-4000:] or f"exit code {process.returncode}"
        raise ConversionError(f"FFmpeg failed: {detail}")
    return stdout


def check_encoder(executable: str, format: str) -> None:
    output = run_ffmpeg([executable, "-hide_banner", "-encoders"])
    names = {parts[1] for line in output.splitlines() if len(parts := line.split()) >= 2}
    if ENCODERS[format] not in names:
        raise ConversionError(f"This FFmpeg build lacks {ENCODERS[format]}, required for {format.upper()}. "
                              "Install an FFmpeg build with that encoder.")


def command(executable: str, frames: Path, destination: Path, format: str,
            fps: float) -> list[str]:
    args = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-framerate", str(fps), "-start_number", "0", "-i", str(frames / "frame-%08d.png"), "-an"]
    if format in ("mp4", "mov"):
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    elif format == "webm":
        args += ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-pix_fmt", "yuv420p"]
    else:
        args += ["-filter_complex", "[0:v]split[a][b];[a]palettegen[p];[b][p]paletteuse",
                 "-loop", "0"]
    return args + ["-f", format, str(destination)]


def publish(temporary: Path, requested: Path) -> Path:
    """Reserve a free name exclusively, then replace only our own reservation."""
    number = 1
    while True:
        candidate = requested if number == 1 else requested.with_name(
            f"{requested.stem}-{number}{requested.suffix}")
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        except FileExistsError:
            number += 1
            continue
        try:
            os.close(fd)
            os.replace(temporary, candidate)
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
        return candidate


def convert(directory: Path, output: Path, format: str, fps: float, executable: str,
            size: tuple[int, int] | None, background: tuple[int, int, int],
            warn: Callable[[str], None], progress: Callable[[str], None]) -> Path:
    collection = inspect(discover(directory), size, format != "gif", warn)
    progress(f"{directory.name}: {len(collection.paths)} frames, "
             f"{collection.canvas[0]}x{collection.canvas[1]}, {fps:g} fps")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Same filesystem as the destination permits atomic replacement of our reservation.
    with tempfile.TemporaryDirectory(prefix=".ic2v-", dir=output.parent) as temporary:
        workspace = Path(temporary)
        prepare(collection, workspace, background)
        progress(f"{directory.name}: encoding {format.upper()}...")
        # Files moved out of TemporaryDirectory retain its private Windows ACL.
        # Stage the video directly beside the destination instead, so it inherits
        # the destination directory's access rules before atomic publication.
        encoded = output.parent / f".ic2v-{uuid.uuid4().hex}.{format}"
        with encoded.open("xb"):
            pass
        try:
            run_ffmpeg(command(executable, workspace, encoded, format, fps))
            if not encoded.is_file() or encoded.stat().st_size == 0:
                raise ConversionError("FFmpeg did not produce a nonempty output file.")
            return publish(encoded, output)
        finally:
            encoded.unlink(missing_ok=True)
