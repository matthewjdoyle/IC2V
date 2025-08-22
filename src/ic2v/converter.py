"""Core conversion functionality for IC2V."""

import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Tuple
import shutil
from PIL import Image
import tempfile
import re


logger = logging.getLogger(__name__)


class FFmpegNotFoundError(Exception):
    """Raised when ffmpeg is not found in the system."""

    pass


class IC2VConverter:
    """Main converter class for IC2V functionality."""

    def __init__(self):
        """Initialize the converter and check for ffmpeg."""
        self.ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable in the system."""
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise FFmpegNotFoundError(
                "ffmpeg not found. Please install ffmpeg and ensure it's in your PATH."
            )
        return ffmpeg_path

    def validate_images(self, image_dir: Path) -> List[Path]:
        """
        Validate and collect PNG images from directory.

        Args:
            image_dir: Directory containing PNG images

        Returns:
            List of valid PNG image paths, sorted naturally

        Raises:
            ValueError: If no valid PNG images found
        """
        if not image_dir.exists():
            raise ValueError(f"Directory does not exist: {image_dir}")

        if not image_dir.is_dir():
            raise ValueError(f"Path is not a directory: {image_dir}")

        # Find all PNG files
        png_files = list(image_dir.glob("*.png")) + list(image_dir.glob("*.PNG"))

        if not png_files:
            raise ValueError(f"No PNG images found in directory: {image_dir}")

        # Sort naturally (handle numeric sequences properly)
        png_files.sort(key=lambda x: self._natural_sort_key(x.name))

        # Validate each image
        valid_images = []
        for img_path in png_files:
            try:
                with Image.open(img_path) as img:
                    # Basic validation - ensure it's a valid image
                    img.verify()
                valid_images.append(img_path)
            except Exception as e:
                logger.warning(f"Skipping invalid image {img_path}: {e}")

        if not valid_images:
            raise ValueError(f"No valid PNG images found in directory: {image_dir}")

        logger.info(f"Found {len(valid_images)} valid PNG images")
        return valid_images

    def _natural_sort_key(self, text: str) -> List:
        """
        Generate a natural sorting key for filenames with numbers.

        Args:
            text: Filename to generate key for

        Returns:
            List that can be used as a sort key
        """

        def tryint(s):
            try:
                return int(s)
            except ValueError:
                return s

        return [tryint(c) for c in re.split(r"(\d+)", text)]

    def get_image_info(self, images: List[Path]) -> Tuple[int, int]:
        """
        Get dimensions from the first image.

        Args:
            images: List of image paths

        Returns:
            Tuple of (width, height)
        """
        with Image.open(images[0]) as img:
            return img.size

    def convert_to_video(
        self,
        image_dir: Path,
        output_path: Path,
        fps: int = 24,
        quality: str = "high",
        codec: str = "libx264",
        progress_callback: Optional[callable] = None,
    ) -> bool:
        """
        Convert PNG images to video using ffmpeg.

        Args:
            image_dir: Directory containing PNG images
            output_path: Output video file path
            fps: Frames per second for output video
            quality: Quality preset ('low', 'medium', 'high', 'lossless')
            codec: Video codec to use
            progress_callback: Optional callback function for progress updates

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Validate inputs
            images = self.validate_images(image_dir)
            width, height = self.get_image_info(images)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create temporary directory with symlinks for ffmpeg
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create numbered symlinks for ffmpeg input
                for i, img_path in enumerate(images):
                    symlink_path = temp_path / f"frame_{i:06d}.png"
                    symlink_path.symlink_to(img_path.absolute())

                # Build ffmpeg command
                input_pattern = str(temp_path / "frame_%06d.png")

                # Quality settings
                quality_settings = self._get_quality_settings(quality)

                cmd = (
                    [
                        self.ffmpeg_path,
                        "-y",  # Overwrite output file
                        "-framerate",
                        str(fps),
                        "-i",
                        input_pattern,
                        "-c:v",
                        codec,
                        "-pix_fmt",
                        "yuv420p",  # Compatible with most players
                        "-r",
                        str(fps),  # Output framerate
                    ]
                    + quality_settings
                    + [str(output_path)]
                )

                logger.info(
                    f"Starting conversion: {len(images)} images -> {output_path}"
                )
                logger.debug(f"FFmpeg command: {' '.join(cmd)}")

                # Run ffmpeg with progress tracking
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )

                # Monitor progress if callback provided
                if progress_callback:
                    self._monitor_ffmpeg_progress(
                        process, len(images), progress_callback
                    )

                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    logger.error(f"FFmpeg failed with return code {process.returncode}")
                    logger.error(f"FFmpeg stderr: {stderr}")
                    return False

                logger.info(f"Conversion completed successfully: {output_path}")
                return True

        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return False

    def _get_quality_settings(self, quality: str) -> List[str]:
        """
        Get ffmpeg quality settings based on preset.

        Args:
            quality: Quality preset name

        Returns:
            List of ffmpeg arguments for quality settings
        """
        quality_presets = {
            "low": ["-crf", "28", "-preset", "fast"],
            "medium": ["-crf", "23", "-preset", "medium"],
            "high": ["-crf", "18", "-preset", "slow"],
            "lossless": ["-crf", "0", "-preset", "veryslow"],
        }

        return quality_presets.get(quality.lower(), quality_presets["medium"])

    def _monitor_ffmpeg_progress(
        self, process: subprocess.Popen, total_frames: int, callback: callable
    ) -> None:
        """
        Monitor ffmpeg progress by parsing stderr output.

        Args:
            process: Running ffmpeg process
            total_frames: Total number of frames to process
            callback: Function to call with progress updates
        """
        # This is a simplified progress monitoring
        # In practice, ffmpeg progress parsing can be complex
        frame_pattern = re.compile(r"frame=\s*(\d+)")

        while process.poll() is None:
            try:
                if process.stderr and process.stderr.readable():
                    line = process.stderr.readline()
                    if line:
                        match = frame_pattern.search(line)
                        if match:
                            current_frame = int(match.group(1))
                            progress = min(current_frame / total_frames, 1.0)
                            callback(progress)
            except Exception:
                # Continue without progress updates if parsing fails
                break
