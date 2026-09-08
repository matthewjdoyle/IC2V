"""
Implements the single-collection and batch conversion commands.

Author: M J Doyle

Public command-line interface.
"""

from pathlib import Path
import sys
from typing import Annotated

import typer

from . import encoding, preferences
from .collection import ConversionError, discover, natural_key, parse_background, parse_size


app = typer.Typer(no_args_is_help=True, help="Convert PNG image collections into videos or GIFs.")
PRESETS = (6, 12, 24, 30)


def warn(message: str) -> None:
    typer.echo(f"Warning: {message}", err=True)


def select_fps(value: str | None) -> float:
    if value is not None:
        fps = preferences.validate_fps(value)
    else:
        if not sys.stdin.isatty():
            raise ValueError("Frame rate is required: use --fps NUMBER when running noninteractively.")
        previous = preferences.read_fps(warn)
        default = str(PRESETS.index(previous) + 1) if previous in PRESETS else ("5" if previous else "2")
        typer.echo("Choose frame rate: 1) 6 fps  2) 12 fps  3) 24 fps  4) 30 fps  5) Custom")
        while True:
            choice = typer.prompt("Selection", default=default)
            if choice in ("1", "2", "3", "4", "5"):
                break
            warn("Choose a number from 1 to 5.")
        if choice == "5":
            while True:
                custom = typer.prompt("Custom FPS", default=str(previous) if previous else None)
                try:
                    fps = preferences.validate_fps(custom)
                    break
                except ValueError as exc:
                    warn(str(exc))
        else:
            fps = float(PRESETS[int(choice) - 1])
    preferences.save_fps(fps, warn)
    return fps


def setup(format: str, fps: str | None, size: str | None,
          background: str, ffmpeg: str | None) -> tuple:
    if format not in encoding.ENCODERS:
        raise ValueError("Unsupported format. Choose mp4, webm, mov, or gif.")
    canvas = parse_size(size)
    color = parse_background(background)
    executable = encoding.resolve_ffmpeg(ffmpeg)
    encoding.check_encoder(executable, format)
    rate = select_fps(fps)
    if format == "gif":
        warn("GIF frame delays have centisecond precision; playback timing may differ from the requested FPS.")
    return rate, executable, canvas, color


Input = Annotated[Path, typer.Argument(help="Directory containing PNG images.", exists=True,
                                      file_okay=False, readable=True)]
FPS = Annotated[str | None, typer.Option(help="Positive frame rate; omitted to select interactively.")]
Size = Annotated[str | None, typer.Option(help="Output canvas WIDTHxHEIGHT; default is largest source dimensions.")]
Background = Annotated[str, typer.Option(help="Opaque padding/transparency background color.")]
FFmpeg = Annotated[str | None, typer.Option("--ffmpeg", help="FFmpeg executable path (default: PATH lookup).")]


@app.command("convert")
def convert_command(
    input_dir: Input,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output .mp4, .webm, .mov, or .gif file.")],
    fps: FPS = None,
    size: Size = None,
    background: Background = "black",
    ffmpeg: FFmpeg = None,
) -> None:
    """Convert one collection. Existing output names receive a numbered suffix."""
    try:
        format = output.suffix.lower().lstrip(".")
        rate, executable, canvas, color = setup(format, fps, size, background, ffmpeg)
        result = encoding.convert(input_dir, output, format, rate, executable,
                                  canvas, color, warn, typer.echo)
        typer.echo(f"Created {result}")
    except (ConversionError, ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("batch")
def batch_command(
    input_root: Input,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Destination directory for generated videos.")],
    format: Annotated[str, typer.Option(help="Output format: mp4, webm, mov, gif.")] = "mp4",
    fps: FPS = None,
    size: Size = None,
    background: Background = "black",
    ffmpeg: FFmpeg = None,
) -> None:
    """Convert each immediate child folder into a separate output."""
    try:
        format = format.lower()
        children = sorted((p for p in input_root.iterdir() if p.is_dir()), key=natural_key)
        rate, executable, canvas, color = setup(format, fps, size, background, ffmpeg)
        succeeded = skipped = failed = 0
        for index, child in enumerate(children, 1):
            typer.echo(f"[{index}/{len(children)}] {child.name}")
            try:
                if not discover(child):
                    typer.echo("Skipped: no PNG images.")
                    skipped += 1
                    continue
                result = encoding.convert(child, output_dir / f"{child.name}.{format}", format,
                                          rate, executable, canvas, color, warn, typer.echo)
                typer.echo(f"Created {result}")
                succeeded += 1
            except (ConversionError, OSError, ValueError) as exc:
                typer.echo(f"Error in {child.name}: {exc}", err=True)
                failed += 1
        typer.echo(f"Summary: {succeeded} succeeded, {skipped} skipped, {failed} failed.")
        if not succeeded and not failed:
            typer.echo("Error: no eligible PNG collections found.", err=True)
        if failed or not succeeded:
            raise typer.Exit(1)
    except (ConversionError, ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
