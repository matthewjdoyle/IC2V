"""Tests for the IC2V CLI module."""

from click.testing import CliRunner
from unittest.mock import patch, Mock

from ic2v.cli import main
from ic2v.converter import FFmpegNotFoundError


class TestCLI:
    """Test cases for CLI functionality."""

    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "IC2V - Image Collection 2 Video Converter" in result.output
        assert "INPUT_DIR" in result.output
        assert "OUTPUT_FILE" in result.output

    def test_cli_version(self):
        """Test CLI version output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_dry_run(self, mock_converter_class, sample_images, temp_dir):
        """Test CLI dry run mode."""
        # Mock converter
        mock_converter = Mock()
        mock_converter.validate_images.return_value = list(sample_images.glob("*.png"))
        mock_converter.get_image_info.return_value = (100, 100)
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"

        result = runner.invoke(
            main, [str(sample_images), str(output_file), "--dry-run"]
        )

        assert result.exit_code == 0
        assert "Dry run mode" in result.output
        # Ensure convert_to_video was not called
        mock_converter.convert_to_video.assert_not_called()

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_successful_conversion(
        self, mock_converter_class, sample_images, temp_dir
    ):
        """Test successful CLI conversion."""
        # Mock converter
        mock_converter = Mock()
        mock_converter.validate_images.return_value = list(sample_images.glob("*.png"))
        mock_converter.get_image_info.return_value = (100, 100)
        mock_converter.convert_to_video.return_value = True
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"
        # Create the output file to simulate successful conversion
        output_file.write_bytes(b"fake video data")

        # Auto-confirm overwrite
        result = runner.invoke(
            main,
            [str(sample_images), str(output_file), "--fps", "30", "--quality", "high"],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "Conversion completed successfully" in result.output
        mock_converter.convert_to_video.assert_called_once()

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_conversion_failure(
        self, mock_converter_class, sample_images, temp_dir
    ):
        """Test CLI conversion failure."""
        # Mock converter that fails
        mock_converter = Mock()
        mock_converter.validate_images.return_value = list(sample_images.glob("*.png"))
        mock_converter.get_image_info.return_value = (100, 100)
        mock_converter.convert_to_video.return_value = False
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"

        result = runner.invoke(main, [str(sample_images), str(output_file)])

        assert result.exit_code != 0
        assert "Conversion failed" in result.output

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_ffmpeg_not_found(self, mock_converter_class, sample_images, temp_dir):
        """Test CLI behavior when ffmpeg is not found."""
        # Mock converter that raises FFmpegNotFoundError
        mock_converter_class.side_effect = FFmpegNotFoundError("ffmpeg not found")

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"

        result = runner.invoke(main, [str(sample_images), str(output_file)])

        assert result.exit_code != 0
        assert "ffmpeg not found" in result.output
        assert "Please install ffmpeg" in result.output

    def test_cli_nonexistent_input_dir(self, temp_dir):
        """Test CLI with non-existent input directory."""
        runner = CliRunner()
        nonexistent_dir = temp_dir / "nonexistent"
        output_file = temp_dir / "output.mp4"

        result = runner.invoke(main, [str(nonexistent_dir), str(output_file)])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_invalid_fps(self, mock_converter_class, sample_images, temp_dir):
        """Test CLI with invalid FPS value."""
        # Mock converter initialization to succeed
        mock_converter = Mock()
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"

        result = runner.invoke(
            main, [str(sample_images), str(output_file), "--fps", "0"]
        )

        assert result.exit_code != 0
        assert "FPS must be positive" in result.output

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_overwrite_confirmation(
        self, mock_converter_class, sample_images, temp_dir
    ):
        """Test CLI overwrite confirmation."""
        # Mock converter
        mock_converter = Mock()
        mock_converter.validate_images.return_value = list(sample_images.glob("*.png"))
        mock_converter.get_image_info.return_value = (100, 100)
        mock_converter.convert_to_video.return_value = True
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"
        # Create existing output file
        output_file.write_text("existing")

        # Test declining overwrite
        result = runner.invoke(
            main, [str(sample_images), str(output_file)], input="n\n"
        )

        assert result.exit_code == 0
        assert "Conversion cancelled" in result.output
        mock_converter.convert_to_video.assert_not_called()

    @patch("ic2v.cli.IC2VConverter")
    def test_cli_verbose_mode(self, mock_converter_class, sample_images, temp_dir):
        """Test CLI verbose mode."""
        # Mock converter
        mock_converter = Mock()
        mock_converter.validate_images.return_value = list(sample_images.glob("*.png"))
        mock_converter.get_image_info.return_value = (100, 100)
        mock_converter.convert_to_video.return_value = True
        mock_converter_class.return_value = mock_converter

        runner = CliRunner()
        output_file = temp_dir / "output.mp4"
        # Don't create output file beforehand to avoid overwrite prompt

        result = runner.invoke(
            main, [str(sample_images), str(output_file), "--verbose"]
        )

        assert result.exit_code == 0
        # In verbose mode, we should see more detailed output
        assert "Conversion completed successfully" in result.output
