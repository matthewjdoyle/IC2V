"""Command-line interface for IC2V."""

import click
import logging
from pathlib import Path
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

from .converter import IC2VConverter, FFmpegNotFoundError


console = Console()


def setup_logging(verbose: bool) -> None:
    """Set up logging with rich formatting."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.command()
@click.argument(
    "input_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option(
    "--fps",
    "-f",
    default=24,
    type=int,
    help="Frames per second for output video (default: 24)",
)
@click.option(
    "--quality",
    "-q",
    type=click.Choice(["low", "medium", "high", "lossless"], case_sensitive=False),
    default="high",
    help="Video quality preset (default: high)",
)
@click.option(
    "--codec", "-c", default="libx264", help="Video codec to use (default: libx264)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be done without actually converting",
)
@click.version_option(version="0.1.0", prog_name="IC2V")
def main(
    input_dir: Path,
    output_file: Path,
    fps: int,
    quality: str,
    codec: str,
    verbose: bool,
    dry_run: bool,
) -> None:
    """
    IC2V - Image Collection 2 Video Converter

    Convert a collection of PNG images into a video file using ffmpeg.

    INPUT_DIR: Directory containing PNG images to convert
    OUTPUT_FILE: Path for the output video file

    Examples:
        ic2v images/ output.mp4
        ic2v images/ output.mp4 --fps 30 --quality high
        ic2v images/ output.mov --codec prores --verbose
    """
    setup_logging(verbose)

    # Display banner
    console.print(
        Panel.fit(
            Text("IC2V - Image Collection 2 Video Converter", style="bold blue"),
            style="blue",
        )
    )

    try:
        # Initialize converter
        converter = IC2VConverter()

        # Validate inputs
        if fps <= 0:
            raise click.BadParameter("FPS must be positive")

        # Validate and collect images
        console.print(f"📁 Scanning directory: [bold]{input_dir}[/bold]")
        images = converter.validate_images(input_dir)

        width, height = converter.get_image_info(images)
        duration = len(images) / fps

        # Display conversion info
        info_text = f"""
[bold]Conversion Settings:[/bold]
• Input directory: {input_dir}
• Output file: {output_file}
• Number of images: {len(images)}
• Resolution: {width}x{height}
• Frame rate: {fps} FPS
• Duration: {duration:.2f} seconds
• Quality: {quality}
• Codec: {codec}
        """
        console.print(Panel(info_text.strip(), title="Conversion Plan", style="green"))

        if dry_run:
            console.print(
                "🔍 [bold yellow]Dry run mode - no conversion performed[/bold yellow]"
            )
            return

        # Confirm if output file exists
        if output_file.exists():
            if not click.confirm(f"Output file '{output_file}' exists. Overwrite?"):
                console.print("❌ Conversion cancelled")
                return

        # Perform conversion with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("Converting images to video...", total=100)

            def progress_callback(percent: float) -> None:
                progress.update(task, completed=percent * 100)

            success = converter.convert_to_video(
                image_dir=input_dir,
                output_path=output_file,
                fps=fps,
                quality=quality,
                codec=codec,
                progress_callback=progress_callback,
            )

            if success:
                console.print(
                    "✅ [bold green]Conversion completed successfully![/bold green]"
                )
                console.print(f"📹 Output: [bold]{output_file}[/bold]")

                # Show file size
                if output_file.exists():
                    file_size = output_file.stat().st_size
                    size_mb = file_size / (1024 * 1024)
                    console.print(f"📊 File size: {size_mb:.1f} MB")
            else:
                console.print("❌ [bold red]Conversion failed![/bold red]")
                raise click.ClickException("Conversion process failed")

    except FFmpegNotFoundError as e:
        console.print(f"❌ [bold red]Error:[/bold red] {e}")
        console.print("\n[yellow]Please install ffmpeg:[/yellow]")
        console.print("• Ubuntu/Debian: [bold]sudo apt install ffmpeg[/bold]")
        console.print("• macOS: [bold]brew install ffmpeg[/bold]")
        console.print("• Windows: Download from https://ffmpeg.org/download.html")
        raise click.ClickException("ffmpeg not found")

    except ValueError as e:
        console.print(f"❌ [bold red]Error:[/bold red] {e}")
        raise click.ClickException(str(e))

    except Exception as e:
        console.print(f"❌ [bold red]Unexpected error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise click.ClickException(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
