"""Test configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path
from PIL import Image


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_images(temp_dir):
    """Create a set of sample PNG images for testing."""
    images_dir = temp_dir / "images"
    images_dir.mkdir()

    # Create sample images with proper RGB color values
    for i in range(5):
        r = min(255, i * 50)
        g = min(255, i * 30)
        b = min(255, i * 70)
        img = Image.new("RGB", (100, 100), color=(r, g, b))
        img.save(images_dir / f"frame_{i:03d}.png")

    return images_dir


@pytest.fixture
def empty_dir(temp_dir):
    """Create an empty directory for testing."""
    empty = temp_dir / "empty"
    empty.mkdir()
    return empty


@pytest.fixture
def invalid_images_dir(temp_dir):
    """Create a directory with invalid 'PNG' files."""
    invalid_dir = temp_dir / "invalid"
    invalid_dir.mkdir()

    # Create a fake PNG file
    fake_png = invalid_dir / "fake.png"
    fake_png.write_text("This is not a real PNG file")

    return invalid_dir
