"""Build a LONG test project: many short scenes (default 800 x ~1.4 s = about 19 minutes).

Creates in OUTPUT_FOLDER:
  voice.mp3              voice-over (tone bursts per word, so every word's true start time is known)
  script.txt             "Scene 1: ..." ... "Scene 800: ..."
  truth.json             true start time of every scene
  fake_transcript.json   what a speech recogniser would return, with ~6% typical mistakes
  media/                 one file per scene: images (PNG/JPG/WEBP, mixed sizes) and every 8th scene a clip

usage:  python tests/make_long_sample.py OUTPUT_FOLDER [SCENES]
"""
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sceneforge import ffmpeg_utils as ff  # noqa: E402

SR = 24000
WORDS = ("the ancient city stone river empire temple gold desert night king queen army secret map tomb "
         "light shadow wall door ship storm island village forest mountain fire water bridge tower road "
         "scroll symbol priest market trade coin sword shield horse wind rain dust moon star sun sea "
         "hidden lost broken silent sacred forgotten golden dark bright distant strange early final "
         "found built crossed buried carried opened burned painted watched followed vanished returned").split()


def build(out, n_scenes=800, seed=3, media=True):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "media").mkdir(parents=True)
    rng = random.Random(seed)
    chunks, truth_words, starts, script = [], [], [], []
    t = 0.5
    chunks.append(np.zeros(int(SR * 0.5), np.float32))
    for n in range(1, n_scenes + 1):
        words = [rng.choice(WORDS) for _ in range(rng.randint(3, 4))]
        if n % 50 == 0:
            words.insert(1, str(1000 + n))  # a number now and then ("1050" is spoken as words)
        script.append(f"Scene {n}: " + " ".join(words).capitalize() + ".")
        starts.append(round(t, 3))
        for w in words:
            dur = 0.18 + 0.025 * min(len(w), 6)
            k = int(SR * dur)
            tt = np.arange(k) / SR
            burst = (0.3 * np.sin(2 * np.pi * (170 + 13 * (sum(map(ord, w)) % 9)) * tt) * np.hanning(k)).astype(np.float32)
            truth_words.append({"w": " " + w, "s": round(t, 3), "e": round(t + dur, 3), "p": 0.95})
            chunks.append(burst)
            t += dur
            g = rng.uniform(0.04, 0.08)
            chunks.append(np.zeros(int(SR * g), np.float32))
            t += g
        g = rng.uniform(0.12, 0.25)
        chunks.append(np.zeros(int(SR * g), np.float32))
        t += g
    chunks.append(np.zeros(int(SR * 1.0), np.float32))
    t += 1.0
    audio = np.concatenate(chunks)
    raw = out / "voice.raw"
    audio.astype("<f4").tofile(raw)
    ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, "-c:a", "libmp3lame", "-b:a", "96k", out / "voice.mp3"])
    raw.unlink()

    # What a recogniser might return: digits for spoken numbers, misspellings, dropped words, split words.
    fake = []
    for i, w in enumerate(truth_words):
        x = dict(w)
        r = rng.random()
        word = x["w"].strip()
        if word.isdigit():
            pass  # recognisers usually write numbers as digits - same as the script here
        elif r < 0.025:
            x["w"] = " " + word[:-1] + ("e" if word[-1] != "e" else "a")  # misspelt
        elif r < 0.04 and i and truth_words[i - 1]["e"] + 0.1 > w["s"]:
            continue  # dropped (only inside a scene)
        elif r < 0.05 and len(word) > 5:
            mid = (x["s"] + x["e"]) / 2
            fake.append({"w": " " + word[:3], "s": x["s"], "e": round(mid, 3), "p": 0.6})
            x = {"w": " " + word[3:], "s": round(mid, 3), "e": x["e"], "p": 0.6}  # heard as two words
        fake.append(x)

    (out / "script.txt").write_text("\n".join(script) + "\n", encoding="utf-8")
    (out / "truth.json").write_text(json.dumps({"scene_starts": starts, "duration": round(len(audio) / SR, 3)}))
    (out / "fake_transcript.json").write_text(json.dumps(fake))

    if not media:
        return
    # media
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 90)
    except Exception:
        font = ImageFont.load_default()
    clip = out / "_clip.mp4"
    ff.run(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=1.2", "-f", "lavfi", "-i",
            "sine=frequency=660:duration=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", clip])
    for n in range(1, n_scenes + 1):
        if n % 8 == 0:
            shutil.copy(clip, out / "media" / f"scene_{n}.mp4")
            continue
        size = [(640, 360), (800, 1000), (1200, 500)][n % 3]
        col = ((n * 47) % 200 + 30, (n * 91) % 200 + 30, (n * 13) % 200 + 30)
        img = Image.new("RGB", size, col)
        d = ImageDraw.Draw(img)
        d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline="white", width=6)
        d.text((size[0] / 2, size[1] / 2), str(n), fill="white", font=font, anchor="mm", stroke_width=4, stroke_fill="black")
        name, ext = [(f"Scene {n}", ".png"), (f"{n:04d}", ".jpg"), (f"scene-{n}", ".webp")][n % 3]
        img.save(out / "media" / (name + ext), quality=85)
    clip.unlink()
    print(f"{n_scenes} scenes, voice {len(audio) / SR / 60:.1f} min, {len(fake)} transcript words -> {out}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "sample_long", int(sys.argv[2]) if len(sys.argv) > 2 else 800)
