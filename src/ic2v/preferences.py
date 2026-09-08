"""
Loads, validates, and saves the user's frame-rate preference.

Author: M J Doyle

"""

import json
import math
import os
from pathlib import Path
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass

from platformdirs import user_config_path


def validate_fps(value: str | float) -> float:
    try:
        fps = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("FPS must be a positive, finite number.") from exc
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("FPS must be a positive, finite number.")
    return fps


def preferences_path() -> Path:
    return user_config_path("ic2v", appauthor=False) / "preferences.json"


@dataclass(frozen=True)
class DesktopPreferences:
    format: str = "mp4"
    fps: float = 12
    automatic_size: bool = True
    size: str = "1920x1080"
    background: str = "black"
    nested_mode: str = "direct"
    image_fit: str = "contain"


def _load_data() -> dict:
    data = json.loads(preferences_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid preference")
    return data


def _write_data(data: dict, warn: Callable[[str], None]) -> None:
    path = preferences_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        warn(f"Could not save preferences: {exc}")
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def read_fps(warn: Callable[[str], None]) -> float | None:
    path = preferences_path()
    try:
        data = _load_data()
        if isinstance(data.get("fps"), bool):
            raise ValueError("Invalid preference")
        return validate_fps(data["fps"])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        warn(f"Could not read saved FPS from {path}; using the initial selection.")
        return None


def save_fps(fps: float, warn: Callable[[str], None]) -> None:
    try:
        data = _load_data()
    except (OSError, ValueError):
        data = {}
    data["fps"] = validate_fps(fps)
    _write_data(data, warn)


def read_desktop(warn: Callable[[str], None]) -> DesktopPreferences:
    path = preferences_path()
    try:
        data = _load_data()
        prefs = DesktopPreferences(
            format=data.get("format", "mp4"),
            fps=validate_fps(data.get("fps", 12)),
            automatic_size=data.get("automatic_size", True),
            size=data.get("size", "1920x1080"),
            background=data.get("background", "black"),
            nested_mode=data.get("nested_mode", "direct"),
            image_fit=data.get("image_fit", "contain"),
        )
        if prefs.format not in ("mp4", "mov", "webm", "gif"):
            raise ValueError("Invalid format")
        if not isinstance(prefs.automatic_size, bool):
            raise ValueError("Invalid canvas preference")
        if prefs.nested_mode not in ("direct", "flatten", "separate"):
            raise ValueError("Invalid nested-folder preference")
        if prefs.image_fit not in ("contain", "shrink", "preserve"):
            raise ValueError("Invalid image fit preference")
        from .collection import parse_background, parse_size
        parse_size(prefs.size)
        parse_background(prefs.background)
        return prefs
    except FileNotFoundError:
        return DesktopPreferences()
    except (OSError, ValueError, TypeError, KeyError):
        warn(f"Could not read saved settings from {path}; using defaults.")
        return DesktopPreferences()


def save_desktop(settings: DesktopPreferences, warn: Callable[[str], None]) -> None:
    data = asdict(settings)
    data["fps"] = validate_fps(settings.fps)
    _write_data(data, warn)
