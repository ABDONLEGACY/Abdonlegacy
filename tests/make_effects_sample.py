"""Sample project for Scene Effects: a map with two pins dropping on two words, and a [TEXT: 1940] scene.

The voice-over is built word by word (FFmpeg's speech synth when available), so the true start time of
every spoken word is known exactly -> the test can check each effect lands on its word.

usage:  python tests/make_effects_sample.py OUTPUT_FOLDER
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from make_sample import tts_word, SR  # noqa: E402

# (spoken words, script text). Markers sit right before the word that triggers them.
SCENES = [
    ("The legions marched from Rome all the way to Carthage across the sea",
     "The legions marched from [PIN: Rome] Rome all the way to [PIN: Carthage] Carthage across the sea."),
    ("Everything changed in nineteen-forty when the war reached the coast",
     "Everything changed in [TEXT: 1940] 1940 when the war reached the coast."),
    ("Today the ruins still stand beside the water",
     "Today the ruins still stand beside the water."),
]
# Where the cities are on the map picture (fractions of width / height)
CITIES = {"Rome": (0.62, 0.28), "Carthage": (0.38, 0.70)}


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_map(path, size=(2000, 1200)):
    w, h = size
    rng = random.Random(5)
    img = Image.new("RGB", size, (70, 130, 180))  # sea
    d = ImageDraw.Draw(img)
    land = (222, 205, 160)
    # northern coast (Italy-ish) and southern coast (Africa-ish)
    d.polygon([(0, 0), (w, 0), (w, h * 0.18), (w * 0.78, h * 0.22), (w * 0.70, h * 0.45), (w * 0.62, h * 0.52),
               (w * 0.58, h * 0.40), (w * 0.50, h * 0.30), (w * 0.30, h * 0.26), (0, h * 0.30)], fill=land)
    d.polygon([(0, h), (w, h), (w, h * 0.80), (w * 0.62, h * 0.82), (w * 0.45, h * 0.66), (w * 0.36, h * 0.64),
               (w * 0.28, h * 0.75), (0, h * 0.72)], fill=land)
    d.ellipse([w * 0.47, h * 0.53, w * 0.55, h * 0.60], fill=land)  # an island
    img = img.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(img)
    for i in range(0, w, 100):
        d.line([(i, 0), (i, h)], fill=(255, 255, 255), width=1)
    for j in range(0, h, 100):
        d.line([(0, j), (w, j)], fill=(255, 255, 255), width=1)
    for _ in range(40):  # small towns
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(120, 100, 80))
    for name, (fx, fy) in CITIES.items():
        x, y = fx * w, fy * h
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(255, 0, 255))  # magenta city dot (easy to find)
        d.text((x + 22, y + 26), name.upper(), fill=(60, 50, 40), font=font(34))
    d.text((w * 0.47, h * 0.47), "MARE NOSTRUM", fill=(230, 240, 255), font=font(40))
    img.save(path)


def make_photo(path, color, title, size=(1920, 1080)):
    w, h = size
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    for i in range(14):
        c = tuple(min(255, int(v * (0.7 + 0.04 * i))) for v in color)
        d.rectangle([w * 0.05 * i, h * 0.55, w * 0.05 * i + w * 0.04, h * (0.95 - 0.02 * (i % 5))], fill=c)
    d.text((w / 2, h * 0.3), title, fill=(255, 255, 255), font=font(110), anchor="mm")
    img.save(path)


def make_sounds(out):
    t = np.arange(int(SR * 0.35)) / SR
    thud = (0.9 * np.sin(2 * np.pi * 95 * t) * np.exp(-t * 18)).astype(np.float32)
    t2 = np.arange(int(SR * 0.18)) / SR
    pop = (0.6 * np.sin(2 * np.pi * (2200 + 9000 * t2) * t2) * np.exp(-t2 * 30)).astype(np.float32)
    for name, x in (("pin_drop.wav", thud), ("text_pop.wav", pop)):
        raw = out / (name + ".raw")
        x.astype("<f4").tofile(raw)
        ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, out / name])
        raw.unlink()


def build(out):
    out = Path(out)
    (out / "media").mkdir(parents=True, exist_ok=True)
    rng = random.Random(9)
    pieces, words, scene_starts, t = [np.zeros(int(SR * 0.5), np.float32)], [], [], 0.5
    for si, (spoken, _script) in enumerate(SCENES):
        if si:
            g = 0.9
            pieces.append(np.zeros(int(SR * g), np.float32))
            t += g
        scene_starts.append(round(t, 3))
        for w in spoken.split():
            a = tts_word(w.replace("-", " "))
            words.append({"w": " " + ("1940" if w == "nineteen-forty" else w), "s": round(t, 3),
                          "e": round(t + len(a) / SR, 3), "p": 1.0})
            pieces.append(a)
            t += len(a) / SR
            g = 0.07 + rng.random() * 0.05
            pieces.append(np.zeros(int(SR * g), np.float32))
            t += g
    pieces.append(np.zeros(int(SR * 1.2), np.float32))
    audio = np.concatenate(pieces)
    raw = out / "voice.raw"
    audio.astype("<f4").tofile(raw)
    ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, "-c:a", "pcm_s16le", out / "voice.wav"])
    raw.unlink()
    script = "\n\n".join(f"Scene {i + 1}: {s[1]}" for i, s in enumerate(SCENES))
    (out / "script.txt").write_text(script, encoding="utf-8")
    (out / "transcript.json").write_text(json.dumps(words, indent=1))  # what the recogniser would hear
    (out / "truth.json").write_text(json.dumps({"words": words, "scene_starts": scene_starts,
                                                "duration": round(len(audio) / SR, 3), "cities": CITIES}))
    make_map(out / "media" / "Scene 1.png")
    make_photo(out / "media" / "Scene 2.jpg", (120, 90, 60), "THE COAST")
    make_photo(out / "media" / "Scene 3.jpg", (60, 90, 120), "RUINS")
    make_sounds(out)
    print(f"Effects sample in {out}: {len(audio) / SR:.1f}s voice, words: "
          + ", ".join(f"{w['w'].strip()}@{w['s']}" for w in words if w["w"].strip() in ("Rome", "Carthage", "1940")))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "sample_effects")
