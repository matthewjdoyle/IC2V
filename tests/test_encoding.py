"""
Tests FFmpeg command handling, output naming, cancellation, and cleanup.

Author: M J Doyle
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ic2v import encoding
from ic2v.collection import ConversionError


def test_numbered_outputs_preserve_existing_files(tmp_path):
    requested = tmp_path / "scene.mp4"
    requested.write_bytes(b"original")
    (tmp_path / "scene-2.mp4").write_bytes(b"second")
    temporary = tmp_path / "temp.mp4"
    temporary.write_bytes(b"new")
    assert encoding.publish(temporary, requested).name == "scene-3.mp4"
    assert requested.read_bytes() == b"original"
    assert (tmp_path / "scene-2.mp4").read_bytes() == b"second"


def test_concurrent_publication_uses_distinct_names(tmp_path):
    requested = tmp_path / "scene.mp4"
    sources = [tmp_path / f"temp{i}.mp4" for i in range(4)]
    for index, source in enumerate(sources):
        source.write_bytes(str(index).encode())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda path: encoding.publish(path, requested), sources))
    assert len(set(results)) == 4
    assert {path.read_bytes() for path in results} == {b"0", b"1", b"2", b"3"}


@pytest.mark.parametrize("error", [ConversionError("encoding failed"), KeyboardInterrupt()])
def test_failed_conversion_cleans_temporary_files(images, tmp_path, monkeypatch, error):
    def fail(*args):
        raise error

    monkeypatch.setattr(encoding, "run_ffmpeg", fail)
    output = tmp_path / "output" / "movie.mp4"
    with pytest.raises(type(error)):
        encoding.convert(images, output, "mp4", 12, "ffmpeg", None, (0, 0, 0), "contain", lambda _: None, lambda _: None)
    assert list(output.parent.iterdir()) == []


def test_missing_encoder(monkeypatch):
    monkeypatch.setattr(encoding, "run_ffmpeg", lambda _: " V..... gif GIF encoder")
    with pytest.raises(ConversionError, match="libx264"):
        encoding.check_encoder("ffmpeg", "mp4")


def test_cancellation_kills_and_reaps_ffmpeg(monkeypatch):
    class Process:
        calls = 0
        killed = False

        def communicate(self):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt()
            return "", ""

        def kill(self):
            self.killed = True

    process = Process()
    monkeypatch.setattr(encoding.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(KeyboardInterrupt):
        encoding.run_ffmpeg(["ffmpeg"])
    assert process.killed
    assert process.calls == 2


def test_token_cancellation_terminates_and_reaps_ffmpeg(monkeypatch):
    class Process:
        returncode = None
        terminated = False

        def communicate(self, timeout=None):
            if timeout == 2:
                self.returncode = 0
                return "", ""
            raise subprocess.TimeoutExpired("ffmpeg", timeout)

        def terminate(self):
            self.terminated = True

        def poll(self):
            return self.returncode

        def kill(self):
            raise AssertionError("graceful termination should have completed")

    import subprocess
    process = Process()
    monkeypatch.setattr(encoding.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(ConversionError, match="cancelled"):
        encoding.run_ffmpeg(["ffmpeg"], lambda: True)
    assert process.terminated
