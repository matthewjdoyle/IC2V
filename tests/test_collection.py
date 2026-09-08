"""
Tests PNG discovery, image inspection, sizing, padding, and validation.

Author: M J Doyle
"""

from pathlib import Path

from PIL import Image
import pytest

from ic2v.collection import ConversionError, discover, inspect, parse_background, parse_size, prepare


def test_natural_order_and_direct_pngs(images):
    (images / "ignored.jpg").touch()
    (images / "nested").mkdir()
    (images / "nested" / "other.png").touch()
    assert [p.name for p in discover(images)] == ["frame1.png", "frame2.PNG", "frame10.png"]


def test_mixed_dimensions_and_even_canvas(images):
    Image.new("RGB", (41, 19)).save(images / "frame1.png")
    warnings = []
    result = inspect(discover(images), None, True, warnings.append)
    assert result.canvas == (42, 24)
    assert any("different dimensions" in warning for warning in warnings)
    assert any("even" in warning for warning in warnings)


def test_padding_transparency_and_explicit_canvas(tmp_path):
    source = tmp_path / "transparent.png"
    Image.new("RGBA", (4, 2), (255, 0, 0, 128)).save(source)
    warnings = []
    collection = inspect([source], (4, 4), False, warnings.append)
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    prepare(collection, prepared, (0, 0, 255))
    with Image.open(prepared / "frame-00000000.png") as frame:
        assert frame.size == (4, 4)
        assert frame.getpixel((0, 0)) == (0, 0, 255)
        assert frame.getpixel((1, 1)) == (128, 0, 127)
    assert any("padding" in warning for warning in warnings)


def test_corrupt_png_reports_path(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a PNG")
    with pytest.raises(ConversionError, match="broken.png"):
        inspect([path], None, True, lambda _: None)


@pytest.mark.parametrize("value", ["0x100", "-1x2", "1920", "1.5x2", "2x0"])
def test_invalid_size(value):
    with pytest.raises(ValueError):
        parse_size(value)


def test_size_and_color():
    assert parse_size("1920x1080") == (1920, 1080)
    assert parse_size(None) is None
    assert parse_background("#abcdef") == (171, 205, 239)
    with pytest.raises(ValueError):
        parse_background("#00000000")
