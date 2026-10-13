"""Where things live on disk, and how to find FFmpeg."""
import json
import os
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_DIR = APP_DIR / "settings"
MODELS_DIR = APP_DIR / "models"
FONTS_DIR = APP_DIR / "fonts"
APP_SETTINGS_FILE = SETTINGS_DIR / "app_settings.json"

IS_WINDOWS = sys.platform.startswith("win")


def _default_projects_dir() -> Path:
    docs = Path.home() / "Documents"
    base = docs if docs.is_dir() else Path.home()
    return base / "SceneForge Projects"


def load_app_settings() -> dict:
    data = {}
    if APP_SETTINGS_FILE.exists():
        try:
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.setdefault("projects_dir", str(_default_projects_dir()))
    return data


def save_app_settings(data: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    APP_SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def projects_dir() -> Path:
    p = Path(os.environ.get("SCENEFORGE_PROJECTS") or load_app_settings()["projects_dir"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def _find_tool(name: str) -> str:
    exe = name + (".exe" if IS_WINDOWS else "")
    local = APP_DIR / "ffmpeg" / "bin" / exe
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    raise RuntimeError(
        f"{name} was not found. Run Install_SceneForge.bat again, "
        f"or put {exe} in the 'ffmpeg\\bin' folder inside SceneForge."
    )


def ffmpeg() -> str:
    return _find_tool("ffmpeg")


def ffprobe() -> str:
    return _find_tool("ffprobe")
