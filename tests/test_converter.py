"""Tests for the IC2V converter module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ic2v.converter import IC2VConverter, FFmpegNotFoundError


class TestIC2VConverter:
    """Test cases for IC2VConverter class."""

    def test_init_with_ffmpeg_available(self):
        """Test converter initialization when ffmpeg is available."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            assert converter.ffmpeg_path == "/usr/bin/ffmpeg"

    def test_init_without_ffmpeg(self):
        """Test converter initialization when ffmpeg is not available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(FFmpegNotFoundError):
                IC2VConverter()

    def test_validate_images_success(self, sample_images):
        """Test successful image validation."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            images = converter.validate_images(sample_images)

            assert len(images) == 5
            assert all(img.suffix.lower() == ".png" for img in images)
            # Check natural sorting
            assert images[0].name == "frame_000.png"
            assert images[-1].name == "frame_004.png"

    def test_validate_images_nonexistent_dir(self):
        """Test validation with non-existent directory."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            nonexistent = Path("/nonexistent/directory")

            with pytest.raises(ValueError, match="Directory does not exist"):
                converter.validate_images(nonexistent)

    def test_validate_images_empty_dir(self, empty_dir):
        """Test validation with directory containing no PNG files."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()

            with pytest.raises(ValueError, match="No PNG images found"):
                converter.validate_images(empty_dir)

    def test_validate_images_file_instead_of_dir(self, temp_dir):
        """Test validation when path is a file instead of directory."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            file_path = temp_dir / "test.txt"
            file_path.write_text("test")

            with pytest.raises(ValueError, match="Path is not a directory"):
                converter.validate_images(file_path)

    def test_natural_sort_key(self):
        """Test natural sorting key generation."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()

            # Test with numeric sequences
            key1 = converter._natural_sort_key("frame_1.png")
            key2 = converter._natural_sort_key("frame_10.png")
            key3 = converter._natural_sort_key("frame_2.png")

            # Should sort numerically, not lexicographically
            assert key1 < key3 < key2

    def test_get_image_info(self, sample_images):
        """Test getting image dimensions."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            images = list(sample_images.glob("*.png"))
            width, height = converter.get_image_info(images)

            assert width == 100
            assert height == 100

    def test_get_quality_settings(self):
        """Test quality settings generation."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()

            low_settings = converter._get_quality_settings("low")
            assert "-crf" in low_settings and "28" in low_settings

            high_settings = converter._get_quality_settings("high")
            assert "-crf" in high_settings and "18" in high_settings

            # Test default fallback
            unknown_settings = converter._get_quality_settings("unknown")
            assert "-crf" in unknown_settings and "23" in unknown_settings

    @patch("subprocess.Popen")
    def test_convert_to_video_success(self, mock_popen, sample_images, temp_dir):
        """Test successful video conversion."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            # Mock successful ffmpeg process
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = ("success", "")
            mock_process.poll.return_value = 0
            mock_popen.return_value = mock_process

            converter = IC2VConverter()
            output_file = temp_dir / "output.mp4"

            result = converter.convert_to_video(
                image_dir=sample_images, output_path=output_file
            )

            assert result is True
            mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_convert_to_video_failure(self, mock_popen, sample_images, temp_dir):
        """Test video conversion failure."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            # Mock failed ffmpeg process
            mock_process = Mock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = ("", "error message")
            mock_popen.return_value = mock_process

            converter = IC2VConverter()
            output_file = temp_dir / "output.mp4"

            result = converter.convert_to_video(
                image_dir=sample_images, output_path=output_file
            )

            assert result is False

    def test_convert_to_video_invalid_images(self, empty_dir, temp_dir):
        """Test conversion with invalid image directory."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            converter = IC2VConverter()
            output_file = temp_dir / "output.mp4"

            result = converter.convert_to_video(
                image_dir=empty_dir, output_path=output_file
            )

            assert result is False
