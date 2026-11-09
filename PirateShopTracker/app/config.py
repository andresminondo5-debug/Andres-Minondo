"""Settings, templates and data folders. Everything lives under %APPDATA%\\PirateShopTracker."""

import json
import os
from pathlib import Path

APP_NAME = "PirateShopTracker"
APP_TITLE = "Pirate Shop Chest Tracker PRO"
GAME_PROCESS = "FortniteClient-Win64-Shipping.exe"

DEFAULT_SETTINGS = {
    "fps": 4,
    "threshold": 0.85,
    "cooldown_seconds": 3.0,
    "auto_start_tracking": True,
    "require_fortnite": True,
    "detector_validated": False,
    "overlay_visible": False,
    "overlay_geometry": [60, 60, 300, 150],
    "overlay_opacity": 0.9,
}


def data_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_dir() -> Path:
    path = data_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def template_path(kind: str) -> Path:
    return templates_dir() / f"{kind}.png"


def _settings_file() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        saved = json.loads(_settings_file().read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    except (OSError, json.JSONDecodeError):
        pass
    return settings


def save_settings(settings: dict) -> None:
    try:
        _settings_file().write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass
