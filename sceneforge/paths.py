"""Where things live on disk, and how to find FFmpeg."""
import json
import os
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_DIR = Path(os.environ.get("SCENEFORGE_SETTINGS") or APP_DIR / "settings")  # env: tests only
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


def safe_replace(src, dst, tries=40, wait=0.15):
    """Move src over dst. On Windows a file can be locked for a moment (OneDrive syncing, antivirus
    scanning, a video player); retry for a few seconds instead of failing."""
    import time
    src, dst = Path(src), Path(dst)
    for i in range(tries):
        try:
            src.replace(dst)
            return dst
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(wait)
    return dst


def safe_unlink(path, tries=10, wait=0.1):
    """Delete a file if possible; a file Windows keeps locked is left for later (never an error)."""
    import time
    path = Path(path)
    for _ in range(tries):
        try:
            path.unlink(missing_ok=True)
            return True
        except PermissionError:
            time.sleep(wait)
        except OSError:
            return False
    return False
