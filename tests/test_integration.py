"""
Verifies real MP4, WebM, MOV, GIF, batch, and Windows ACL conversions.

Author: M J Doyle
"""

import subprocess
import sys

from PIL import Image, ImageSequence
import pytest
from typer.testing import CliRunner

from ic2v.cli import app
from ic2v.service import ConversionRequest, NestedMode, convert_request, plan_collections


@pytest.mark.integration
@pytest.mark.parametrize("format", ["mp4", "webm", "mov", "gif"])
def test_formats_frame_order_dimensions_timing_and_collisions(images, tmp_path, ffmpeg, format):
    output = tmp_path / "output with spaces" / f"movie.{format}"
    runner = CliRunner()
    args = ["convert", str(images), "-o", str(output), "--fps", "12", "--ffmpeg", ffmpeg]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    original = output.read_bytes()
    assert original

    # Decode to fixed-size RGB frames to verify dimensions, count, and natural order.
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(output), "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-vsync", "0", "-"], capture_output=True, check=True).stdout
    frame_bytes = 32 * 24 * 3
    assert len(decoded) == frame_bytes * 3
    pixels = [decoded[i * frame_bytes:i * frame_bytes + 3] for i in range(3)]
    assert pixels[0][0] > 200 and pixels[0][1] < 30
    assert pixels[1][1] > 80 and pixels[1][0] < 30
    assert pixels[2][2] > 200 and pixels[2][0] < 30

    if format == "gif":
        with Image.open(output) as gif:
            duration = sum(frame.info.get("duration", 0) for frame in ImageSequence.Iterator(gif)) / 1000
            assert abs(duration - 3 / 12) < 0.04
    else:
        metadata = subprocess.run([ffmpeg, "-hide_banner", "-i", str(output)], capture_output=True, text=True).stderr
        import re
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", metadata)
        assert match, metadata
        duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
        assert abs(duration - 3 / 12) < 0.04

    again = runner.invoke(app, args)
    assert again.exit_code == 0, again.output
    assert output.read_bytes() == original
    assert output.with_stem("movie-2").is_file()
    assert not list(output.parent.glob(".ic2v-*"))


@pytest.mark.integration
def test_real_batch_mixed_images_and_corrupt_collection(tmp_path, ffmpeg):
    root = tmp_path / "collections"
    for name in ("scene1", "scene2", "empty"):
        (root / name).mkdir(parents=True)
    (root / "scene1" / "broken.png").write_bytes(b"corrupt")
    Image.new("RGB", (31, 20), "red").save(root / "scene2" / "frame1.png")
    Image.new("RGBA", (20, 25), (0, 255, 0, 128)).save(root / "scene2" / "frame2.png")
    output_dir = tmp_path / "videos"
    result = CliRunner().invoke(app, ["batch", str(root), "--output-dir", str(output_dir),
                                     "--fps", "6", "--ffmpeg", ffmpeg])
    assert result.exit_code == 1, result.output
    assert "broken.png" in result.output
    assert "different dimensions" in result.output
    assert "padding may appear" in result.output
    assert "32x26" in result.output
    assert "1 succeeded, 1 skipped, 1 failed" in result.output
    assert [path.name for path in output_dir.iterdir()] == ["scene2.mp4"]
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(output_dir / "scene2.mp4"),
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-vsync", "0", "-"],
                             capture_output=True, check=True).stdout
    assert len(decoded) == 32 * 26 * 3 * 2


@pytest.mark.integration
def test_recursive_flatten_encodes_naturally_ordered_nested_frames(tmp_path, ffmpeg):
    root = tmp_path / "experiment"
    scene2 = root / "scene2"
    scene10 = root / "scene10"
    scene2.mkdir(parents=True)
    scene10.mkdir(parents=True)
    Image.new("RGB", (16, 16), "red").save(root / "frame1.png")
    Image.new("RGB", (16, 16), "green").save(scene2 / "frame1.png")
    Image.new("RGB", (16, 16), "blue").save(scene10 / "frame1.png")
    job = plan_collections([root], NestedMode.FLATTEN)[0]
    output = tmp_path / "flattened.mp4"
    result = convert_request(ConversionRequest(
        root, output, fps=6, ffmpeg=ffmpeg, paths=job.paths,
    ))
    assert result.output == output
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(output), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-vsync", "0", "-"],
        capture_output=True, check=True,
    ).stdout
    frame_bytes = 16 * 16 * 3
    pixels = [decoded[index * frame_bytes:index * frame_bytes + 3] for index in range(3)]
    assert pixels[0][0] > 200 and pixels[0][1] < 30
    assert pixels[1][1] > 80 and pixels[1][0] < 30
    assert pixels[2][2] > 200 and pixels[2][0] < 30


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "win32", reason="Windows ACL regression")
def test_video_inherits_destination_read_access(images, tmp_path, ffmpeg):
    output_dir = tmp_path / "shared-videos"
    output_dir.mkdir()
    # Give the local Users group read access to this generated test directory.
    # Private TemporaryDirectory ACLs must not replace that access on publication.
    subprocess.run(["icacls", str(output_dir), "/grant", "*S-1-5-32-545:(OI)(CI)(RX)"],
                   capture_output=True, check=True)
    output = output_dir / "movie.mp4"
    result = CliRunner().invoke(app, ["convert", str(images), "-o", str(output),
                                     "--fps", "6", "--ffmpeg", ffmpeg])
    assert result.exit_code == 0, result.output
    permissions = subprocess.run(["icacls", str(output)], capture_output=True, check=True,
                                  text=True, errors="replace").stdout
    assert "(I)(RX)" in permissions, permissions
