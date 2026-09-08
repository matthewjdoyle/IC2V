"""
UI-independent conversion requests, progress events, and cancellation.

Author: M J Doyle
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
import threading

from . import encoding
from .collection import (
    ConversionError, discover, discover_collections, discover_recursive,
    parse_background, parse_size,
)


class Phase(str, Enum):
    INSPECTING = "inspecting"
    PREPARING = "preparing"
    ENCODING = "encoding"
    WARNING = "warning"
    COMPLETE = "complete"


class NestedMode(str, Enum):
    DIRECT = "direct"
    FLATTEN = "flatten"
    SEPARATE = "separate"


@dataclass(frozen=True)
class PlannedCollection:
    source_root: Path
    input_dir: Path
    paths: tuple[Path, ...]
    label: str
    output_stem: str

    @property
    def frame_count(self) -> int:
        return len(self.paths)


@dataclass(frozen=True)
class ConversionRequest:
    input_dir: Path
    output: Path
    format: str = "mp4"
    fps: float = 12
    size: tuple[int, int] | None = None
    background: tuple[int, int, int] = (0, 0, 0)
    image_fit: str = "contain"
    ffmpeg: str | None = None
    paths: tuple[Path, ...] | None = None


@dataclass(frozen=True)
class ConversionResult:
    input_dir: Path
    output: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgressEvent:
    phase: Phase
    message: str
    completed: int | None = None
    total: int | None = None


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


def default_output(input_dir: Path, format: str, output_dir: Path | None = None) -> Path:
    parent = output_dir if output_dir is not None else input_dir.parent
    return parent / f"{input_dir.name}.{format.lower()}"


def plan_collections(roots: list[Path], mode: NestedMode) -> list[PlannedCollection]:
    """Resolve selected roots into concrete conversion jobs for the desktop UI."""
    jobs: list[PlannedCollection] = []
    for root in roots:
        if mode == NestedMode.DIRECT:
            paths = tuple(discover(root))
            jobs.append(PlannedCollection(root, root, paths, root.name, root.name))
        elif mode == NestedMode.FLATTEN:
            paths = tuple(discover_recursive(root))
            jobs.append(PlannedCollection(root, root, paths, root.name, root.name))
        else:
            groups = discover_collections(root)
            if not groups:
                jobs.append(PlannedCollection(root, root, (), root.name, root.name))
                continue
            for directory, paths in groups:
                relative = directory.relative_to(root)
                if relative.parts:
                    label = f"{root.name} / {' / '.join(relative.parts)}"
                    stem = " - ".join((root.name, *relative.parts))
                else:
                    label = root.name
                    stem = root.name
                jobs.append(PlannedCollection(root, directory, tuple(paths), label, stem))
    return jobs


def bundled_ffmpeg() -> str | None:
    """Return the FFmpeg shipped with a frozen desktop build, if present."""
    roots = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).parent)
    for root in roots:
        candidates = [root / "ffmpeg.exe", *root.glob("ffmpeg*.exe")]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def desktop_ffmpeg() -> str:
    packaged = bundled_ffmpeg()
    if packaged:
        return packaged
    try:
        import imageio_ffmpeg
        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(candidate).is_file():
            return candidate
    except (ImportError, OSError):
        pass
    return encoding.resolve_ffmpeg(None)


def validate_request(request: ConversionRequest) -> None:
    if not request.input_dir.is_dir():
        raise ConversionError(f"Input directory does not exist: {request.input_dir}")
    if request.format not in encoding.ENCODERS:
        raise ValueError("Unsupported format. Choose mp4, webm, mov, or gif.")
    if request.output.suffix.lower() != f".{request.format}":
        raise ValueError(f"Output must have a .{request.format} extension.")
    from .preferences import validate_fps
    validate_fps(request.fps)
    if request.size is not None:
        parse_size(f"{request.size[0]}x{request.size[1]}")
    if (not isinstance(request.background, tuple) or len(request.background) != 3
            or any(isinstance(value, bool) or not isinstance(value, int)
                   or not 0 <= value <= 255 for value in request.background)):
        raise ValueError("Background must contain three color values from 0 to 255.")


def convert_request(
    request: ConversionRequest,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    token: CancellationToken | None = None,
    verify_encoder: bool = True,
) -> ConversionResult:
    validate_request(request)
    emit = on_progress or (lambda _event: None)
    cancel = token or CancellationToken()
    executable = request.ffmpeg or desktop_ffmpeg()
    if verify_encoder:
        encoding.check_encoder(executable, request.format)
    warnings: list[str] = []

    def warn(message: str) -> None:
        warnings.append(message)
        emit(ProgressEvent(Phase.WARNING, message))

    def message(value: str) -> None:
        phase = Phase.ENCODING if "encoding " in value else Phase.INSPECTING
        emit(ProgressEvent(phase, value))

    def frames(completed: int, total: int) -> None:
        emit(ProgressEvent(Phase.PREPARING, f"Preparing frame {completed} of {total}",
                           completed, total))

    emit(ProgressEvent(Phase.INSPECTING, f"Inspecting {request.input_dir.name}"))
    output = encoding.convert(
        request.input_dir, request.output, request.format, request.fps, executable,
        request.size, request.background, request.image_fit, warn, message, frames, cancel.is_cancelled,
        request.paths,
    )
    emit(ProgressEvent(Phase.COMPLETE, f"Created {output}", 1, 1))
    return ConversionResult(request.input_dir, output, tuple(warnings))
