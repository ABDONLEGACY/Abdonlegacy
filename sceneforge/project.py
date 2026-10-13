"""A project = one folder holding inputs, settings, timings and output."""
import copy
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from . import paths, presets
from .script_parser import natural_key

PROJECT_FILE = "project.json"


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().strip(".")
    return name[:80] or "Untitled"


class Project:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.data = {}

    # ---- folders ------------------------------------------------------------
    @property
    def voice_dir(self):
        return self.dir / "inputs" / "voice"

    @property
    def media_dir(self):
        return self.dir / "inputs" / "media"

    @property
    def audio_dir(self):
        return self.dir / "inputs" / "audio"

    @property
    def work_dir(self):
        return self.dir / "work"

    @property
    def output_dir(self):
        return self.dir / "output"

    def path(self, rel):
        return None if not rel else self.dir / rel

    def rel(self, p):
        return str(Path(p).resolve().relative_to(self.dir.resolve())).replace("\\", "/")

    # ---- load / save ----------------------------------------------------------
    @classmethod
    def create(cls, name, aspect, preset_name):
        folder = paths.projects_dir() / safe_name(name)
        if (folder / PROJECT_FILE).exists():
            raise ValueError(f"A project called '{safe_name(name)}' already exists. Open it, or pick another name.")
        p = cls(folder)
        for d in (p.voice_dir, p.media_dir, p.audio_dir, p.work_dir, p.output_dir):
            d.mkdir(parents=True, exist_ok=True)
        settings = presets.get(preset_name)
        settings["aspect"] = aspect
        p.data = {
            "name": name,
            "created": time.strftime("%Y-%m-%d %H:%M"),
            "aspect": aspect,
            "preset": preset_name,
            "settings": settings,
            "seed": int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16),
            "voice_files": [],
            "audio_duration": 0.0,
            "script_text": "",
            "expected_scenes": None,
            "scenes": [],
            "sync": {"done": False},
            "music": None,
            "sfx": None,
            "render": {"resolution": "1080p", "quality": "standard"},
        }
        p.save()
        return p

    @classmethod
    def open(cls, folder):
        p = cls(folder)
        f = p.dir / PROJECT_FILE
        if not f.exists():
            raise FileNotFoundError(f"No project found in {folder}")
        p.data = json.loads(f.read_text(encoding="utf-8"))
        p.data["settings"] = presets.normalize(p.data.get("settings"))
        for d in (p.voice_dir, p.media_dir, p.audio_dir, p.work_dir, p.output_dir):
            d.mkdir(parents=True, exist_ok=True)
        return p

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / (PROJECT_FILE + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.dir / PROJECT_FILE)

    @staticmethod
    def list_all():
        root = paths.projects_dir()
        items = []
        for d in root.iterdir():
            if (d / PROJECT_FILE).exists():
                items.append((d.stat().st_mtime, d.name))
        return [n for _, n in sorted(items, reverse=True)]

    # ---- convenience -----------------------------------------------------------
    @property
    def settings(self):
        return self.data["settings"]

    @property
    def scenes(self):
        return self.data["scenes"]

    def scene(self, number):
        return next((s for s in self.scenes if s["number"] == number), None)

    def size(self, resolution=None):
        res = resolution or self.data.get("render", {}).get("resolution", "1080p")
        long_side, short_side = (3840, 2160) if res == "4K" else ((1280, 720) if res == "720p" else (1920, 1080))
        if self.data["aspect"] == "9:16":
            return short_side, long_side
        return long_side, short_side

    def copy_in(self, src, dest_dir, new_name=None):
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = Path(src)
        dest = dest_dir / (new_name or src.name)
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        return dest

    # ---- scenes ------------------------------------------------------------------
    def set_script(self, text, parsed_scenes, expected):
        old = {s["number"]: s for s in self.scenes}
        new = []
        for s in parsed_scenes:
            o = old.get(s["number"], {})
            new.append({
                "number": s["number"], "text": s["text"],
                "start": None, "auto_start": None, "flag": "", "confidence": None,
                "media": o.get("media"),
            })
        self.data["script_text"] = text
        self.data["expected_scenes"] = expected
        self.data["scenes"] = new
        self.data["sync"] = {"done": False}
        self.save()

    def apply_sync(self, result, model, language):
        for sc, r in zip(self.scenes, result["scenes"]):
            sc["auto_start"] = r["start"]
            sc["start"] = r["start"]
            sc["flag"] = r["flag"]
            sc["confidence"] = r["confidence"]
            sc["method"] = r.get("method", "")
        self.data["sync"] = {"done": True, "model": model, "language": language,
                             "match_rate": result["match_rate"]}
        (self.work_dir / "words.json").write_text(json.dumps(result["words"]), encoding="utf-8")
        self.save()

    def words(self):
        f = self.work_dir / "words.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return []

    def timeline(self):
        """List of dicts (number, start, end, duration) covering 0 .. audio length with no gaps."""
        total = float(self.data.get("audio_duration") or 0)
        rows = []
        for i, sc in enumerate(self.scenes):
            start = 0.0 if i == 0 else float(sc["start"] or 0)
            rows.append({"number": sc["number"], "start": start})
        for i, r in enumerate(rows):
            r["end"] = rows[i + 1]["start"] if i + 1 < len(rows) else total
            r["duration"] = r["end"] - r["start"]
        return rows

    def timeline_problems(self):
        probs = []
        for r in self.timeline():
            if r["duration"] <= 0.05:
                probs.append(f"Scene {r['number']} has no length (starts at or after the next scene).")
        return probs

    def media_files(self):
        return sorted((p for p in self.media_dir.iterdir() if p.is_file()), key=lambda p: natural_key(p.name))

    def voice_files(self):
        return [self.dir / v for v in self.data.get("voice_files", [])]

    def settings_copy(self):
        return copy.deepcopy(self.settings)
