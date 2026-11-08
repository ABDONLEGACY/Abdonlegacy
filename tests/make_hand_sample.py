"""Sample project for the "Hand-lettered + underline" [TEXT] style.

Scene 1 uses YOUR picture (pass its path) with [TEXT: William Donovan]; scene 2 a generated picture with a
busy title painted in it, with [TEXT: 1985]. The voice-over is built word by word, so every word's true
start time is known.

usage:  python tests/make_hand_sample.py OUTPUT_FOLDER PICTURE_FOR_SCENE_1
"""
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from make_effects_sample import make_photo, make_sounds  # noqa: E402
from make_sample import SR, tts_word  # noqa: E402

SCENES = [
    ("In nineteen-seventeen William Donovan led his men across the mud",
     "In 1917 [TEXT: William Donovan] William Donovan led his men across the mud."),
    ("By nineteen-eighty-five the old coast had changed forever",
     "By [TEXT: 1985] 1985 the old coast had changed forever."),
]
DIGITS = {"nineteen-seventeen": "1917", "nineteen-eighty-five": "1985"}


def make_scribble(out):
    rng = np.random.default_rng(3)
    n = int(SR * 0.5)
    noise = rng.standard_normal(n).astype(np.float32)
    # soft, papery marker sound: band-limited noise with a little rhythm, fading in and out
    k = np.ones(24, np.float32) / 24
    soft = np.convolve(noise, k, mode="same") - np.convolve(noise, np.ones(4) / 4, mode="same") * 0.3
    t = np.arange(n) / SR
    env = np.sin(np.pi * t / t[-1]) ** 0.6 * (0.75 + 0.25 * np.sin(2 * np.pi * 9 * t))
    x = (soft * env * 0.5).astype(np.float32)
    raw = out / "scribble.raw"
    x.astype("<f4").tofile(raw)
    ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, out / "marker_scribble.wav"])
    raw.unlink()


def build(out, picture):
    out = Path(out)
    (out / "media").mkdir(parents=True, exist_ok=True)
    rng = random.Random(4)
    pieces, words, t = [np.zeros(int(SR * 0.5), np.float32)], [], 0.5
    for si, (spoken, _s) in enumerate(SCENES):
        if si:
            pieces.append(np.zeros(int(SR * 0.9), np.float32))
            t += 0.9
        for w in spoken.split():
            a = tts_word(w.replace("-", " "))
            words.append({"w": " " + DIGITS.get(w, w), "s": round(t, 3), "e": round(t + len(a) / SR, 3), "p": 1.0})
            pieces.append(a)
            t += len(a) / SR
            g = 0.07 + rng.random() * 0.05
            pieces.append(np.zeros(int(SR * g), np.float32))
            t += g
    pieces.append(np.zeros(int(SR * 2.0), np.float32))
    audio = np.concatenate(pieces)
    raw = out / "voice.raw"
    audio.astype("<f4").tofile(raw)
    ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, "-c:a", "pcm_s16le", out / "voice.wav"])
    raw.unlink()
    (out / "script.txt").write_text("\n\n".join(f"Scene {i + 1}: {s[1]}" for i, s in enumerate(SCENES)), encoding="utf-8")
    (out / "transcript.json").write_text(json.dumps(words, indent=1))
    (out / "truth.json").write_text(json.dumps({"words": words, "duration": round(len(audio) / SR, 3)}))
    shutil.copy(picture, out / "media" / ("Scene 1" + Path(picture).suffix.lower()))
    make_photo(out / "media" / "Scene 2.jpg", (120, 90, 60), "THE COAST")
    make_sounds(out)
    make_scribble(out)
    print(f"Hand-lettering sample in {out}: {len(audio) / SR:.1f}s voice")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
