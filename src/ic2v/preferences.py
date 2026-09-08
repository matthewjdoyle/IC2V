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


def read_fps(warn: Callable[[str], None]) -> float | None:
    path = preferences_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or isinstance(data.get("fps"), bool):
            raise ValueError("Invalid preference")
        return validate_fps(data["fps"])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        warn(f"Could not read saved FPS from {path}; using the initial selection.")
        return None


def save_fps(fps: float, warn: Callable[[str], None]) -> None:
    path = preferences_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"fps": fps}, stream)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        warn(f"Could not save FPS preference: {exc}")
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Preference cleanup is best effort, like preference persistence.
