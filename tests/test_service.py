"""
Tests the UI-independent desktop conversion contract.

Author: M J Doyle
"""

from pathlib import Path

import pytest

from ic2v import encoding
from ic2v.collection import ConversionCancelled
from ic2v.service import (
    CancellationToken, ConversionRequest, NestedMode, Phase, convert_request,
    default_output, plan_collections, validate_request,
)


def test_default_output_is_beside_collection(tmp_path):
    source = tmp_path / "shot one"
    assert default_output(source, "mp4") == tmp_path / "shot one.mp4"
    assert default_output(source, "gif", tmp_path / "exports") == tmp_path / "exports" / "shot one.gif"


def test_nested_modes_plan_direct_flattened_and_separate_jobs(tmp_path):
    root = tmp_path / "project"
    first = root / "scene1"
    second = root / "scene2" / "take1"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (root / "cover.png").touch()
    (first / "frame1.png").touch()
    (first / "frame2.png").touch()
    (second / "frame1.png").touch()

    direct = plan_collections([root], NestedMode.DIRECT)
    assert len(direct) == 1 and direct[0].frame_count == 1
    flattened = plan_collections([root], NestedMode.FLATTEN)
    assert len(flattened) == 1 and flattened[0].frame_count == 4
    separate = plan_collections([root], NestedMode.SEPARATE)
    assert [(job.label, job.frame_count, job.output_stem) for job in separate] == [
        ("project", 1, "project"),
        ("project / scene1", 2, "project - scene1"),
        ("project / scene2 / take1", 1, "project - scene2 - take1"),
    ]


def test_request_emits_structured_progress_and_warnings(images, tmp_path, monkeypatch):
    monkeypatch.setattr(encoding, "check_encoder", lambda *_: None)

    def fake_convert(*args):
        warn, message, frames = args[8], args[9], args[10]
        warn("Mixed dimensions")
        message("input images: 3 frames, 32x24, 12 fps")
        frames(2, 3)
        message("input images: encoding MP4...")
        args[1].parent.mkdir(parents=True, exist_ok=True)
        args[1].write_bytes(b"video")
        return args[1]

    monkeypatch.setattr(encoding, "convert", fake_convert)
    output = tmp_path / "out" / "movie.mp4"
    events = []
    result = convert_request(
        ConversionRequest(images, output, ffmpeg="ffmpeg"), events.append,
    )
    assert result.output == output
    assert result.warnings == ("Mixed dimensions",)
    assert [event.phase for event in events] == [
        Phase.INSPECTING, Phase.WARNING, Phase.INSPECTING,
        Phase.PREPARING, Phase.ENCODING, Phase.COMPLETE,
    ]
    assert events[3].completed == 2
    assert events[3].total == 3


@pytest.mark.parametrize("changes", [
    {"format": "avi"},
    {"fps": 0},
    {"background": (0, 0, 999)},
    {"output": Path("movie.gif")},
])
def test_request_validation(images, tmp_path, changes):
    values = dict(input_dir=images, output=tmp_path / "movie.mp4")
    values.update(changes)
    with pytest.raises((ValueError, TypeError)):
        validate_request(ConversionRequest(**values))


def test_cancelled_request_never_starts_ffmpeg(images, tmp_path, monkeypatch):
    monkeypatch.setattr(encoding, "check_encoder", lambda *_: None)
    token = CancellationToken()
    token.cancel()
    with pytest.raises(ConversionCancelled):
        convert_request(
            ConversionRequest(images, tmp_path / "movie.mp4", ffmpeg="ffmpeg"),
            token=token,
        )
    assert not (tmp_path / "movie.mp4").exists()
