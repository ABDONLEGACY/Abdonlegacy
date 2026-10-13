"""High-level steps used by the UI (and the tests): one function per wizard action."""
import shutil
from pathlib import Path

from . import align, audio, media, script_parser, transcribe
from .project import Project
from .script_parser import natural_key


def save_voice(project: Project, files):
    """Copy voice files into the project (joined in natural file-name order) and build voice.wav."""
    files = [Path(f) for f in files if f]
    if not files:
        raise ValueError("Please upload at least one voiceover file (MP3, WAV or M4A).")
    for f in files:
        if f.suffix.lower() not in media.AUDIO_EXT:
            raise ValueError(f"{f.name} is not an audio file. Use MP3, WAV or M4A.")
    if project.voice_dir.exists():
        shutil.rmtree(project.voice_dir)
    project.voice_dir.mkdir(parents=True)
    copied = [project.copy_in(f, project.voice_dir) for f in sorted(files, key=lambda p: natural_key(p.name))]
    dur = audio.join_voice(copied, project.work_dir / "voice.wav")
    project.data["voice_files"] = [project.rel(c) for c in copied]
    project.data["audio_duration"] = round(dur, 3)
    project.data["sync"] = {"done": False}
    project.save()
    return dur


def check_script(text, expected=None):
    scenes, warnings = script_parser.parse_scenes(text or "")
    if expected and scenes and len(scenes) != int(expected):
        warnings.insert(0, f"You expected {int(expected)} scenes but the script has {len(scenes)}.")
    return scenes, warnings


def save_script(project: Project, text, expected=None):
    scenes, warnings = check_script(text, expected)
    if not scenes:
        raise ValueError(warnings[0] if warnings else "No scenes found in the script.")
    if len(scenes) > 400:
        raise ValueError("More than 400 scenes found - is the script labelled correctly?")
    (project.dir / "inputs").mkdir(exist_ok=True)
    (project.dir / "inputs" / "script.txt").write_text(text, encoding="utf-8")
    project.set_script(text, scenes, int(expected) if expected else None)
    auto_match_media(project)
    return scenes, warnings


def run_sync(project: Project, model="small", language="en", progress=None, transcript_words=None):
    """Transcribe the voiceover (or use given words, for tests) and align it with the script."""
    if not project.scenes:
        raise ValueError("Add the script first (step 2).")
    voice = project.work_dir / "voice.wav"
    if not voice.exists():
        raise ValueError("Add the voiceover first (step 2).")
    if transcript_words is None:
        transcript_words = transcribe.transcribe(voice, project.work_dir, model, language,
                                                 duration=project.data["audio_duration"], progress=progress)
    if not transcript_words:
        raise ValueError("No speech was found in the voiceover.")
    if progress:
        progress(0.99, "Matching script to the voice ...")
    result = align.sync(project.scenes, transcript_words, project.data["audio_duration"],
                        lead_in=float(project.settings["sync"].get("lead_in", 0.0)))
    project.apply_sync(result, model, language)
    return result


def import_media(project: Project, files):
    """Copy media files into the project and match them to scenes. Returns (matched, unmatched, notes)."""
    copied = []
    for f in files:
        f = Path(f)
        if f.is_dir():
            copied += import_media(project, [x for x in f.iterdir() if x.is_file()])[3]
            continue
        if media.media_kind(f):
            copied.append(project.copy_in(f, project.media_dir))
    mapping, unmatched, notes = auto_match_media(project, only=copied)
    return mapping, unmatched, notes, copied


def auto_match_media(project: Project, only=None):
    files = only if only is not None else project.media_files()
    mapping, unmatched, notes = media.match_files(files)
    nums = {s["number"] for s in project.scenes}
    extra = sorted(n for n in mapping if n not in nums)
    if extra:
        notes.append(f"Files for scenes that are not in the script were ignored: {extra[:20]}")
    for sc in project.scenes:
        if sc["number"] in mapping:
            sc["media"] = project.rel(mapping[sc["number"]])
    project.save()
    return mapping, unmatched, notes


def set_scene_media(project: Project, number, file):
    f = Path(file)
    if not media.media_kind(f):
        raise ValueError("Use a PNG, JPG, WEBP, MP4 or MOV file.")
    dest = project.copy_in(f, project.media_dir / "swapped", new_name=f"scene_{number}{f.suffix.lower()}")
    project.scene(number)["media"] = project.rel(dest)
    project.save()


def missing_media(project: Project):
    out = []
    for s in project.scenes:
        p = project.path(s.get("media"))
        if not p or not p.exists():
            out.append(s["number"])
    return out


def nudge(project: Project, number, delta=None, absolute=None):
    """Move a scene's start time. Returns the new start time."""
    idx = next(i for i, s in enumerate(project.scenes) if s["number"] == number)
    if idx == 0:
        raise ValueError("Scene 1 always starts at 0:00 (the start of the video).")
    sc = project.scenes[idx]
    new = float(absolute) if absolute is not None else float(sc["start"] or 0) + float(delta or 0)
    prev_start = 0.0 if idx == 1 else float(project.scenes[idx - 1]["start"] or 0)
    nxt = project.scenes[idx + 1]["start"] if idx + 1 < len(project.scenes) else project.data["audio_duration"]
    lo, hi = prev_start + 0.1, float(nxt) - 0.1
    if hi <= lo:
        raise ValueError("There is no room to move this scene.")
    new = round(min(max(new, lo), hi), 3)
    sc["start"] = new
    sc["edited"] = True
    project.save()
    return new


def reset_start(project: Project, number):
    sc = project.scene(number)
    sc["start"] = sc.get("auto_start")
    sc["edited"] = False
    project.save()
    return sc["start"]
