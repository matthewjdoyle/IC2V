"""
Discovers, validates, sizes, and normalizes PNG image collections.

Author: M J Doyle
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re

from PIL import Image, ImageColor, ImageOps, UnidentifiedImageError


class ConversionError(Exception):
    """An actionable conversion failure safe to display to the user."""


class ConversionCancelled(ConversionError):
    """Raised when a conversion is cancelled before publication."""


def natural_key(path: Path) -> tuple:
    pieces = re.split(r"(\d+)", path.name.casefold())
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in pieces), path.name


def discover(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ConversionError(f"Input directory does not exist: {directory}")
    return sorted((p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".png"),
                  key=natural_key)


def relative_natural_key(path: Path, root: Path) -> tuple:
    """Naturally sort every component of a path relative to a collection root."""
    return tuple(natural_key(Path(part)) for part in path.relative_to(root).parts)


def discover_recursive(directory: Path) -> list[Path]:
    """Find PNGs at every depth without following directory symlinks."""
    if not directory.is_dir():
        raise ConversionError(f"Input directory does not exist: {directory}")
    try:
        paths = [path for path in directory.rglob("*")
                 if path.is_file() and path.suffix.lower() == ".png"]
    except OSError as exc:
        raise ConversionError(f"Could not inspect nested folders in {directory}: {exc}") from exc
    return sorted(paths, key=lambda path: relative_natural_key(path, directory))


def discover_collections(directory: Path) -> list[tuple[Path, list[Path]]]:
    """Return every directory below root that directly contains PNG frames."""
    paths = discover_recursive(directory)
    grouped: dict[Path, list[Path]] = {}
    for path in paths:
        grouped.setdefault(path.parent, []).append(path)
    return sorted(grouped.items(), key=lambda item: relative_natural_key(item[0], directory))


def parse_size(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"([1-9]\d*)[xX]([1-9]\d*)", value)
    if not match:
        raise ValueError("Size must be WIDTHxHEIGHT with positive integer dimensions.")
    return int(match[1]), int(match[2])


def parse_background(value: str) -> tuple[int, int, int]:
    try:
        rgba = ImageColor.getcolor(value, "RGBA")
    except ValueError as exc:
        raise ValueError("Background must be a solid color name or hex color, e.g. black or '#ffffff'.") from exc
    if rgba[3] != 255:
        raise ValueError("Background must be opaque.")
    return rgba[:3]


@dataclass(frozen=True)
class Collection:
    paths: list[Path]
    dimensions: list[tuple[int, int]]
    canvas: tuple[int, int]


def inspect(paths: list[Path], size: tuple[int, int] | None, video: bool,
            warn: Callable[[str], None]) -> Collection:
    if not paths:
        raise ConversionError("No PNG images found in this collection.")
    dimensions = []
    for path in paths:
        try:
            with Image.open(path) as frame:
                if frame.format != "PNG":
                    raise ValueError("File is not a PNG image")
                frame.load()
                dimensions.append(frame.size)
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ConversionError(f"Cannot read PNG image {path}: {exc}") from exc
    canvas = size or (max(w for w, _ in dimensions), max(h for _, h in dimensions))
    if video:
        even = tuple(n + n % 2 for n in canvas)
        if even != canvas:
            warn(f"Rounding canvas to even video dimensions: {even[0]}x{even[1]}.")
        canvas = even
    if len(set(dimensions)) > 1:
        warn("Source images have different dimensions; padding may appear to preserve aspect ratio.")
    elif any(w * canvas[1] != h * canvas[0] for w, h in dimensions):
        warn("The output canvas has a different aspect ratio; padding will appear.")
    return Collection(paths, dimensions, canvas)


def prepare(collection: Collection, directory: Path,
            background: tuple[int, int, int],
            progress: Callable[[int, int], None] | None = None,
            cancelled: Callable[[], bool] | None = None) -> None:
    for index, path in enumerate(collection.paths):
        if cancelled is not None and cancelled():
            raise ConversionCancelled("Conversion cancelled.")
        try:
            with Image.open(path) as source:
                fitted = ImageOps.contain(source.convert("RGBA"), collection.canvas,
                                          method=Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", collection.canvas, background)
                offset = ((canvas.width - fitted.width) // 2, (canvas.height - fitted.height) // 2)
                canvas.paste(fitted, offset, fitted.getchannel("A"))
                canvas.save(directory / f"frame-{index:08d}.png")
                if progress is not None:
                    progress(index + 1, len(collection.paths))
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ConversionError(f"Could not prepare image {path}: {exc}") from exc
