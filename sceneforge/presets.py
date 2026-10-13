"""Style presets (one per channel). Stored in settings/presets.json, editable in the UI."""
import copy
import json

from . import paths

PRESETS_FILE = paths.SETTINGS_DIR / "presets.json"

MOTION_TYPES = ["zoom_in", "zoom_out", "pan_left", "pan_right", "zoom_in_pan", "zoom_out_pan"]
TRANSITION_TYPES = ["fade", "slide_left", "slide_right", "zoom_in", "zoom_out"]
CLIP_FIT_MODES = ["slow_then_freeze", "slow_then_loop", "freeze", "loop"]

BASE = {
    "aspect": "16:9",
    "motion": {
        "zoom_min": 1.06, "zoom_max": 1.15,          # how far images zoom (1.10 = 10 %)
        "pan_min": 0.04, "pan_max": 0.08,            # pan distance as a fraction of frame width
        "types": list(MOTION_TYPES),
        "easing": ["ease_in_out", "linear", "ease_out", "ease_in_out_sine"],
    },
    "transitions": {
        "mode": "rotate",          # rotate | lock | cut
        "types": list(TRANSITION_TYPES),
        "lock_type": "fade",
        "duration": 0.5,
    },
    "clips": {
        "fit_mode": "slow_then_freeze",
        "max_slowdown": 0.20,      # slow a short clip by up to 20 % before freezing / looping
        "keep_audio": False,
        "clip_volume": 0.25,
    },
    "captions": {
        "enabled": True,
        "mode": "word",            # word (highlight) | phrase | single
        "font": "Arial Bold",
        "size": 64,                # pixels at 1080p
        "color": "#FFFFFF",
        "highlight_color": "#FFD400",
        "outline_color": "#000000",
        "outline": 5,
        "shadow": True,
        "position": "bottom",      # bottom | middle
        "max_words": 4,
        "uppercase": False,
        "pop": True,
    },
    "audio": {
        "music_volume": 0.15,
        "duck": True,
        "sfx_volume": 0.6,
    },
    "sync": {
        "lead_in": 0.0,            # cut this many seconds before the first word (0 = exactly on it)
    },
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


DEFAULT_PRESETS = {
    "Documentary": _merge(BASE, {
        "motion": {"zoom_min": 1.04, "zoom_max": 1.10, "pan_min": 0.03, "pan_max": 0.06,
                   "easing": ["ease_in_out_sine", "linear", "ease_in_out"]},
        "transitions": {"mode": "rotate", "types": ["fade", "zoom_in", "zoom_out"], "duration": 0.7},
        "clips": {"fit_mode": "slow_then_freeze", "keep_audio": True, "clip_volume": 0.25},
        "captions": {"enabled": True, "mode": "phrase", "size": 52, "outline": 3,
                     "highlight_color": "#FFFFFF", "max_words": 5, "pop": False},
    }),
    "Animated Explainer": _merge(BASE, {
        "motion": {"zoom_min": 1.06, "zoom_max": 1.15, "pan_min": 0.04, "pan_max": 0.08},
        "transitions": {"mode": "rotate", "types": list(TRANSITION_TYPES), "duration": 0.5},
        "captions": {"enabled": True, "mode": "word", "size": 70, "outline": 6,
                     "highlight_color": "#FFD400", "max_words": 4, "uppercase": True},
    }),
    "POV Finance": _merge(BASE, {
        "motion": {"zoom_min": 1.08, "zoom_max": 1.20, "pan_min": 0.05, "pan_max": 0.10},
        "transitions": {"mode": "rotate", "types": ["slide_left", "slide_right", "zoom_in", "zoom_out"],
                        "duration": 0.5},
        "captions": {"enabled": True, "mode": "word", "size": 66, "outline": 5,
                     "highlight_color": "#3CFF6B", "max_words": 3},
    }),
}


def normalize(preset: dict) -> dict:
    """Fill any missing keys from the defaults so older/hand-edited files keep working."""
    return _merge(BASE, preset or {})


def load_all() -> dict:
    if not PRESETS_FILE.exists():
        save_all(DEFAULT_PRESETS)
    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        # Broken file: keep a backup and restore defaults so the app still starts.
        PRESETS_FILE.replace(PRESETS_FILE.with_suffix(".broken.json"))
        save_all(DEFAULT_PRESETS)
        data = copy.deepcopy(DEFAULT_PRESETS)
    if not data:
        data = copy.deepcopy(DEFAULT_PRESETS)
    return {name: normalize(p) for name, p in data.items()}


def save_all(presets: dict) -> None:
    paths.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PRESETS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(presets, indent=2), encoding="utf-8")
    tmp.replace(PRESETS_FILE)


def names() -> list:
    return list(load_all().keys())


def get(name: str) -> dict:
    allp = load_all()
    if name in allp:
        return allp[name]
    return normalize(DEFAULT_PRESETS.get(name) or next(iter(allp.values())))


def save(name: str, preset: dict) -> None:
    allp = load_all()
    allp[name] = normalize(preset)
    save_all(allp)


def duplicate(name: str, new_name: str) -> None:
    allp = load_all()
    if new_name in allp:
        raise ValueError(f"A preset called '{new_name}' already exists.")
    allp[new_name] = copy.deepcopy(allp[name])
    save_all(allp)


def rename(name: str, new_name: str) -> None:
    allp = load_all()
    if new_name in allp:
        raise ValueError(f"A preset called '{new_name}' already exists.")
    allp = {(new_name if k == name else k): v for k, v in allp.items()}
    save_all(allp)


def delete(name: str) -> None:
    allp = load_all()
    if len(allp) <= 1:
        raise ValueError("You must keep at least one preset.")
    allp.pop(name, None)
    save_all(allp)


def reset_defaults() -> None:
    allp = load_all()
    allp.update(copy.deepcopy(DEFAULT_PRESETS))
    save_all(allp)
