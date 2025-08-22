# IC2V - Image Collection 2 Video Converter

[![CI/CD](https://github.com/matthewjdoyle/IC2V/workflows/CI/CD/badge.svg)](https://github.com/matthewjdoyle/IC2V/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

IC2V (Image Collection 2 Video) is a professional-grade, ffmpeg-based command-line tool for converting collections of PNG images into videos. Perfect for stop-motion animation, time-lapse videos, and any workflow requiring image sequence to video conversion.

## Features

- 🎬 **Professional Video Output**: High-quality video generation using ffmpeg
- 🚀 **Multiple Quality Presets**: Low, medium, high, and lossless options
- 📊 **Progress Tracking**: Real-time conversion progress with elegant UI
- 🔧 **Flexible Configuration**: Customizable frame rates, codecs, and quality settings
- 🖼️ **Smart Image Handling**: Natural sorting, validation, and dimension detection
- 📱 **Rich CLI Interface**: Beautiful command-line interface with helpful output
- ✅ **Comprehensive Testing**: Full test coverage with pytest
- 🏗️ **Professional Packaging**: Ready for distribution via pip

## Installation

### Prerequisites

IC2V requires ffmpeg to be installed on your system:

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

### Install IC2V

```bash
pip install ic2v
```

Or install from source:
```bash
git clone https://github.com/matthewjdoyle/IC2V.git
cd IC2V
pip install -e .
```

## Quick Start

Convert a directory of PNG images to MP4:

```bash
ic2v images/ output.mp4
```

With custom settings:
```bash
ic2v images/ output.mp4 --fps 30 --quality high --verbose
```

## Usage

```
Usage: ic2v [OPTIONS] INPUT_DIR OUTPUT_FILE

  IC2V - Image Collection 2 Video Converter
  
  Convert a collection of PNG images into a video file using ffmpeg.

Options:
  -f, --fps INTEGER               Frames per second for output video (default: 24)
  -q, --quality [low|medium|high|lossless]
                                  Video quality preset (default: high)
  -c, --codec TEXT               Video codec to use (default: libx264)
  -v, --verbose                  Enable verbose logging
  -n, --dry-run                  Show what would be done without converting
  --version                      Show the version and exit.
  --help                         Show this message and exit.
```

### Examples

**Basic conversion:**
```bash
ic2v my_frames/ animation.mp4
```

**High frame rate with lossless quality:**
```bash
ic2v frames/ smooth_animation.mp4 --fps 60 --quality lossless
```

**ProRes codec for professional workflows:**
```bash
ic2v frames/ professional.mov --codec prores --fps 24
```

**Dry run to preview settings:**
```bash
ic2v frames/ test.mp4 --dry-run --verbose
```

## Image Requirements

- **Format**: PNG files (case-insensitive)
- **Naming**: Files are sorted naturally (frame_1.png, frame_2.png, ..., frame_10.png)
- **Consistency**: All images should have the same dimensions
- **Location**: All images must be in a single directory

## Quality Presets

| Preset | CRF | Preset | Use Case |
|--------|-----|--------|----------|
| low | 28 | fast | Quick previews, small file sizes |
| medium | 23 | medium | Balanced quality and size |
| high | 18 | slow | High quality output (default) |
| lossless | 0 | veryslow | Maximum quality, large files |

## Development

### Setup Development Environment

```bash
git clone https://github.com/matthewjdoyle/IC2V.git
cd IC2V
pip install -e .[dev]
```

### Run Tests

```bash
pytest tests/ -v --cov=ic2v
```

### Code Formatting

```bash
black src tests
flake8 src tests
mypy src/ic2v
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Format code (`black src tests`)
7. Commit changes (`git commit -m 'Add amazing feature'`)
8. Push to branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### v0.1.0 (2024-01-01)
- Initial release
- Core image-to-video conversion functionality
- Professional CLI interface
- Multiple quality presets
- Comprehensive test suite
- CI/CD pipeline

## Support

- 📄 [Documentation](https://github.com/matthewjdoyle/IC2V)
- 🐛 [Issue Tracker](https://github.com/matthewjdoyle/IC2V/issues)
- 💬 [Discussions](https://github.com/matthewjdoyle/IC2V/discussions)

---

Made with ❤️ for the creative community
