"""Premium effects: [STAMP] [TYPE] [NOTE] [CIRCLE] [QUOTE] [SHAKE] [CHAPTER] [OPENING].

Builds its own small sample (the effects sample: map + two photos, voice built word by word), renders it at a
small size and checks: markers parse, each effect appears on its word (not before), the chapter scene opens with
the paper tear, the opening is put in front with its sounds, and the built-in sounds land on their words.

usage:  python tests/test_premium.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_premium"))
shutil.rmtree(TMP, ignore_errors=True)
os.environ["SCENEFORGE_PROJECTS"] = str(TMP / "projects")
os.environ["SCENEFORGE_SETTINGS"] = str(TMP / "settings")
sys.path.insert(0, str(ROOT))

from sceneforge import effects, film, paths, pipeline, script_parser  # noqa: E402
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from sceneforge.project import Project  # noqa: E402
from sceneforge.render import Renderer  # noqa: E402

W, H, FPS = 640, 360, 30
SCRIPT = """[OPENING: THE ENTIRE HISTORY OF ROME | TEST CHANNEL · EP 1]

Scene 1: The legions marched from [STAMP: ROME] Rome all the way to [CIRCLE] Carthage across the sea.
Scene 2: [CHAPTER: The war] Everything changed in [TYPE: THE YEAR 1940] 1940 when the [NOTE: war reached the coast] war reached the coast.
Scene 3: Today the [QUOTE: The ruins still stand. | A visitor] ruins still [SHAKE] stand beside the water.
"""


def frame(video, t):
    raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}", "-i",
                          str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8)[:W * H * 3].reshape(H, W, 3).astype(np.int16)


def test_parser():
    scenes, warn = script_parser.parse_scenes(SCRIPT)
    assert not warn, warn
    kinds = [e["type"] for s in scenes for e in s.get("effects", [])]
    assert kinds == ["stamp", "circle", "type", "note", "quote", "shake"], kinds
    assert scenes[1]["chapter"] == "The war" and "chapter" not in scenes[0]
    q = scenes[2]["effects"][0]
    assert q["text"] == "The ruins still stand." and q["attr"] == "A visitor", q
    assert "[" not in " ".join(s["text"] for s in scenes)
    assert script_parser.parse_opening(SCRIPT) == {"title": "THE ENTIRE HISTORY OF ROME", "stamp": "TEST CHANNEL · EP 1"}
    _, warn = script_parser.parse_scenes("Scene 1: a [STAMP] b")
    assert warn and "needs words" in warn[0]
    print("parser ok")


def main():
    test_parser()
    fx = TMP / "sample"
    subprocess.run([sys.executable, str(ROOT / "tests" / "make_effects_sample.py"), str(fx)], check=True,
                   capture_output=True)
    p = Project.create("Premium demo", "16:9", "Under The Logo")
    pipeline.save_voice(p, [fx / "voice.wav"])
    pipeline.save_script(p, SCRIPT, 3)
    pipeline.run_sync(p, transcript_words=json.loads((fx / "transcript.json").read_text()))
    pipeline.import_media(p, sorted(x for x in fx.iterdir() if x.suffix.lower() in (".png", ".jpg")))
    assert p.data["opening"]["title"] == "THE ENTIRE HISTORY OF ROME"
    out = Renderer(p, size=(W, H), tag="t", quality="fast").run()
    O = film.Opening(p.data["opening"]["title"], p.data["opening"]["stamp"], W, H)
    off = round(O.duration * FPS) / FPS
    dur = ff.duration(out)
    assert abs(dur - (off + p.data["audio_duration"])) < 0.15, (dur, off, p.data["audio_duration"])
    print(f"opening {off:.2f}s in front, total {dur:.2f}s")
    # the opening: typed title on paper, then the stamp
    a, b = frame(out, O.TYPE_START - 0.2), frame(out, O.type_end + 0.05)
    assert np.abs(a - b).mean() > 1.0, "the title was not typed"
    # each effect appears on its word, not before
    res = effects.resolve(p)
    for num, items in res.items():
        for e in items:
            if e["type"] == "shake":
                continue
            before, after = frame(out, off + e["t"] - 0.25), frame(out, off + e["t"] + (1.6 if e["type"] == "quote" else 0.6))
            diff = np.abs(before - after).mean()
            print(f"  scene {num} {e['type']:7s} on '{e['word']}' at {e['t']:.2f}s: picture change {diff:.1f}")
            assert diff > 2.0, f"{e['type']} did not show"
    # the chapter scene starts with the paper tear: half-way through the tear, the middle column is torn open
    tl = {r["number"]: r for r in p.timeline()}
    mid = frame(out, off + tl[2]["start"] + 0.06)
    assert mid.std() > 10
    # built-in sounds: the stamp lands on "Rome"
    st = next(e for e in res[1] if e["type"] == "stamp")
    sr = 48000
    audio = ff.read_audio_f32(out, sr=sr)
    level = lambda t0, t1: float(np.abs(audio[int(t0 * sr):int(t1 * sr)]).mean())  # noqa: E731
    fx_only = TMP / "projects" / "Premium demo" / "work" / "render_t" / "fx_track.wav"
    track = ff.read_audio_f32(fx_only, sr=sr)
    tlev = lambda t0, t1: float(np.abs(track[int(t0 * sr):int(t1 * sr)]).max())  # noqa: E731
    assert tlev(st["t"] - 0.02, st["t"] + 0.2) > 5 * tlev(st["t"] - 0.6, st["t"] - 0.3) + 1e-4, "stamp sound not on its word"
    assert level(0.6, O.type_end) > 1e-4, "no typewriter sound in the opening"
    print("sounds ok")
    print("PREMIUM EFFECTS TESTS PASSED -", out)


if __name__ == "__main__":
    main()
