"""Match media files to scenes by the number in the file name."""
import re
from pathlib import Path

from .script_parser import natural_key

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

SCENE_NUM_RE = re.compile(r"scene[\s_\-.#]*0*(\d+)", re.IGNORECASE)
ANY_NUM_RE = re.compile(r"(\d+)")


def media_kind(path) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return ""


def scene_number_from_name(name: str):
    stem = Path(name).stem
    m = SCENE_NUM_RE.search(stem)
    if m:
        return int(m.group(1))
    m = ANY_NUM_RE.search(stem)
    if m:
        return int(m.group(1))
    return None


def match_files(files):
    """files: iterable of paths. Returns (mapping {scene_number: path}, unmatched list, notes list)."""
    mapping, unmatched, notes = {}, [], []
    for f in sorted((Path(x) for x in files), key=lambda p: natural_key(p.name)):
        if not media_kind(f):
            continue
        n = scene_number_from_name(f.name)
        if n is None:
            unmatched.append(f.name)
            continue
        if n in mapping:
            notes.append(f"Scene {n}: two files found ({Path(mapping[n]).name} and {f.name}); using {f.name}.")
        mapping[n] = str(f)
    return mapping, unmatched, notes
