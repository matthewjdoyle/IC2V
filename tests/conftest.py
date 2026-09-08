"""
Defines shared pytest fixtures for image, preference, and FFmpeg tests.

Author: M J Doyle
"""

import os
from pathlib import Path
import shutil

from PIL import Image
import pytest

from ic2v import preferences


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    path = tmp_path / "config" / "preferences.json"
    monkeypatch.setattr(preferences, "preferences_path", lambda: path)
    return path


@pytest.fixture
def images(tmp_path):
    directory = tmp_path / "input images"
    directory.mkdir()
    for name, color in [("frame10.png", "blue"), ("frame2.PNG", "green"), ("frame1.png", "red")]:
        Image.new("RGB", (32, 24), color).save(directory / name)
    return directory


@pytest.fixture
def ffmpeg():
    executable = os.environ.get("IC2V_TEST_FFMPEG") or shutil.which("ffmpeg")
    if not executable:
        pytest.skip("Set IC2V_TEST_FFMPEG or install FFmpeg to run integration tests")
    return str(Path(executable).resolve())
