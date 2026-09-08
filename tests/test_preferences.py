"""
Tests frame-rate validation, persistence, corruption handling, and failures.

Author: M J Doyle
"""

import pytest

from ic2v import preferences


@pytest.mark.parametrize("value", ["0", "-2", "nan", "inf", "no", "1e999"])
def test_invalid_fps(value):
    with pytest.raises(ValueError):
        preferences.validate_fps(value)


def test_roundtrip_and_missing_preferences(isolated_preferences):
    warnings = []
    assert preferences.read_fps(warnings.append) is None
    preferences.save_fps(23.976, warnings.append)
    assert preferences.read_fps(warnings.append) == 23.976
    assert not warnings


@pytest.mark.parametrize("content", ["{oops", "[]", '{"fps": true}', '{"fps": -2}', "{}"])
def test_corrupt_preferences(isolated_preferences, content):
    isolated_preferences.parent.mkdir()
    isolated_preferences.write_text(content)
    warnings = []
    assert preferences.read_fps(warnings.append) is None
    assert len(warnings) == 1


def test_preference_write_failure_is_nonfatal(isolated_preferences, monkeypatch):
    def fail(*args, **kwargs):
        raise PermissionError("read-only config directory")

    monkeypatch.setattr(preferences.os, "replace", fail)
    warnings = []
    preferences.save_fps(12, warnings.append)
    assert len(warnings) == 1
    assert not isolated_preferences.exists()
    assert not list(isolated_preferences.parent.iterdir())


def test_desktop_preferences_roundtrip_and_cli_fps_preservation(isolated_preferences):
    warnings = []
    settings = preferences.DesktopPreferences(
        "webm", 24, False, "640x480", "#123456", "separate",
    )
    preferences.save_desktop(settings, warnings.append)
    assert preferences.read_desktop(warnings.append) == settings
    preferences.save_fps(30, warnings.append)
    assert preferences.read_desktop(warnings.append) == preferences.DesktopPreferences(
        "webm", 30, False, "640x480", "#123456", "separate")
    assert not warnings


def test_old_fps_only_preferences_migrate_to_desktop_defaults(isolated_preferences):
    preferences.save_fps(24, lambda _: None)
    assert preferences.read_desktop(lambda _: None) == preferences.DesktopPreferences(fps=24)
