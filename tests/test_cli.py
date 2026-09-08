"""
Tests command-line FPS selection, validation, errors, and batching.

Author: M J Doyle
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ic2v import cli, encoding, preferences
from ic2v.collection import ConversionError


runner = CliRunner()


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    monkeypatch.setattr(encoding, "resolve_ffmpeg", lambda _: "ffmpeg")
    monkeypatch.setattr(encoding, "check_encoder", lambda *_: None)


def test_explicit_fps_skips_prompt(images, fake_ffmpeg, monkeypatch):
    monkeypatch.setattr(encoding, "convert", lambda *args: args[1])
    result = runner.invoke(cli.app, ["convert", str(images), "-o", "out.mp4", "--fps", "7.5"])
    assert result.exit_code == 0, result.output
    assert "Selection" not in result.output
    assert preferences.read_fps(lambda _: None) == 7.5


@pytest.mark.parametrize("previous,answers,expected", [(24, "\n", 24), (7.5, "\n\n", 7.5),
                                                     (23.97612345, "\n\n", 23.97612345),
                                                     (None, "5\n0\n8.5\n", 8.5)])
def test_interactive_fps(previous, answers, expected, monkeypatch):
    if previous is not None:
        preferences.save_fps(previous, lambda _: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    # Isolate the prompt behavior from FFmpeg and filesystem checks.
    import typer
    app = typer.Typer()

    @app.command()
    def choose():
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        typer.echo(f"Chosen: {cli.select_fps(None):g}")

    result = runner.invoke(app, [], input=answers)
    assert result.exit_code == 0, result.output
    assert f"Chosen: {expected:g}" in result.output
    assert preferences.read_fps(lambda _: None) == expected


def test_noninteractive_requires_fps(images, fake_ffmpeg):
    result = runner.invoke(cli.app, ["convert", str(images), "-o", "out.mp4"])
    assert result.exit_code == 1
    assert "--fps NUMBER" in result.output


@pytest.mark.parametrize("arguments,expected", [(["-o", "out.avi", "--fps", "12"], "Unsupported format"),
    (["-o", "out.mp4", "--fps", "0"], "positive"),
    (["-o", "out.mp4", "--fps", "12", "--size", "0x2"], "WIDTHxHEIGHT")])
def test_invalid_arguments(images, fake_ffmpeg, arguments, expected):
    result = runner.invoke(cli.app, ["convert", str(images), *arguments])
    assert result.exit_code == 1
    assert expected in result.output


def test_missing_ffmpeg(images, monkeypatch):
    monkeypatch.setattr(encoding.shutil, "which", lambda _: None)
    result = runner.invoke(cli.app, ["convert", str(images), "-o", "out.mp4", "--fps", "12"])
    assert result.exit_code == 1
    assert "--ffmpeg PATH" in result.output


def test_batch_continues_and_summarizes(tmp_path, fake_ffmpeg, monkeypatch):
    root = tmp_path / "batch"
    root.mkdir()
    for name in ["scene1", "scene2", "empty"]:
        (root / name).mkdir()
    (root / "scene1" / "frame.png").touch()
    (root / "scene2" / "frame.png").touch()
    calls = []

    def convert(*args):
        calls.append(args[0].name)
        if args[0].name == "scene1":
            raise ConversionError("Broken image")
        return args[1]

    monkeypatch.setattr(encoding, "convert", convert)
    result = runner.invoke(cli.app, ["batch", str(root), "--output-dir", str(tmp_path / "out"), "--fps", "12"])
    assert result.exit_code == 1
    assert calls == ["scene1", "scene2"]
    assert "1 succeeded, 1 skipped, 1 failed" in result.output


def test_empty_batch_fails(tmp_path, fake_ffmpeg):
    result = runner.invoke(cli.app, ["batch", str(tmp_path), "--output-dir", str(tmp_path / "out"), "--fps", "12"])
    assert result.exit_code == 1
    assert "no eligible" in result.output
