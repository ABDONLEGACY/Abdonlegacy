"""Create a small test project: generated voiceover (2 parts), 5-scene script, images, one clip, music, whoosh.

The voiceover is built word by word with FFmpeg's built-in speech synth (flite) when available, so the
true start time of every word is known exactly. That lets the tests check sync accuracy.

usage:  python tests/make_sample.py OUTPUT_FOLDER
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from sceneforge import paths  # noqa: E402

SR = 48000
SCRIPT = [
    "The ancient city was buried under the sand for two thousand years.",
    "In nineteen twenty two, explorers finally found the hidden entrance.",
    "Inside, they discovered walls covered with strange golden symbols.",
    "Nobody could read them, and the mystery deepened every single day.",
    "Today, scientists believe the symbols describe a forgotten calendar.",
]


def has_flite():
    out = subprocess.run([paths.ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " flite " in out


def tts_word(word):
    """Return float32 mono samples at 48k for one word."""
    if has_flite():
        safe = word.replace("'", "").replace(":", "")
        proc = ff.run(["-f", "lavfi", "-i", f"flite=text='{safe}':voice=slt", "-ac", "1", "-ar", SR,
                       "-f", "f32le", "-"], desc="tts")
        data = np.frombuffer(proc.stdout, dtype=np.float32).copy()
        # trim leading/trailing near-silence so we know the word's true start
        idx = np.where(np.abs(data) > 0.01)[0]
        if len(idx):
            data = data[max(0, idx[0] - 48):idx[-1] + 48]
        return data
    # Fallback: a tone burst per word (length by word length)
    n = int(SR * (0.18 + 0.05 * len(word)))
    t = np.arange(n) / SR
    f = 180 + 20 * (hash(word) % 10)
    return (0.3 * np.sin(2 * np.pi * f * t) * np.hanning(n)).astype(np.float32)


def build_voice(out_dir: Path):
    rng = random.Random(7)
    pieces, truth_words, t = [], [], 0.0
    pieces.append(np.zeros(int(SR * 0.6), np.float32)); t += 0.6
    scene_starts = []
    for si, line in enumerate(SCRIPT):
        if si > 0:
            gap = 0.7 + rng.random() * 0.5
            pieces.append(np.zeros(int(SR * gap), np.float32)); t += gap
        scene_starts.append(round(t, 3))
        for w in line.split():
            a = tts_word(w)
            truth_words.append({"w": " " + w, "s": round(t, 3), "e": round(t + len(a) / SR, 3), "p": 1.0})
            pieces.append(a); t += len(a) / SR
            g = 0.06 + rng.random() * 0.06
            pieces.append(np.zeros(int(SR * g), np.float32)); t += g
    pieces.append(np.zeros(int(SR * 1.0), np.float32)); t += 1.0
    audio = np.concatenate(pieces)
    # Split into two files at a silence between scene 3 and 4 to test joining.
    cut = int(round((scene_starts[3] - 0.3) * SR))
    for name, part in (("voice_part1.wav", audio[:cut]), ("voice_part2.wav", audio[cut:])):
        raw = out_dir / (name + ".raw")
        part.astype("<f4").tofile(raw)
        ff.run(["-f", "f32le", "-ar", SR, "-ac", 1, "-i", raw, "-c:a", "pcm_s16le", out_dir / name])
        raw.unlink()
    return truth_words, scene_starts, len(audio) / SR


def fake_transcript(truth_words):
    """Simulate typical transcription mistakes: a misspelt word, digits for numbers, a merged word, a dropped word."""
    out = []
    for w in truth_words:
        out.append(dict(w))
    words = [w["w"].strip() for w in out]
    # numbers as digits: "nineteen twenty two" -> "1922"
    i = words.index("nineteen")
    merged = {"w": " 1922,", "s": out[i]["s"], "e": out[i + 2]["e"], "p": 0.9}
    out = out[:i] + [merged] + out[i + 3:]
    for w in out:
        if w["w"].strip().rstrip(".,") == "golden":
            w["w"] = " goldan"
        if w["w"].strip().rstrip(".,") == "Nobody":
            w["w"] = " No body"  # split differently
        if w["w"].strip().rstrip(".,") == "deepened":
            w["w"] = " deep and"
    out = [w for w in out if w["w"].strip() != "single"]  # dropped word
    return out


def make_image(path, text, color, size):
    w, h = size
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    for i in range(0, w, 80):
        d.line([(i, 0), (i, h)], fill=tuple(min(255, c + 40) for c in color), width=3)
    for j in range(0, h, 80):
        d.line([(0, j), (w, j)], fill=tuple(min(255, c + 40) for c in color), width=3)
    d.ellipse([w * 0.35, h * 0.25, w * 0.65, h * 0.75], outline="white", width=12)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(h / 6))
    except Exception:
        font = ImageFont.load_default()
    d.text((w / 2, h / 2), text, fill="white", font=font, anchor="mm", stroke_width=4, stroke_fill="black")
    img.save(path)


def build(out_dir):
    out_dir = Path(out_dir)
    (out_dir / "media").mkdir(parents=True, exist_ok=True)
    truth, starts, total = build_voice(out_dir)
    (out_dir / "truth.json").write_text(json.dumps({"words": truth, "scene_starts": starts, "duration": total}, indent=1))
    (out_dir / "fake_transcript.json").write_text(json.dumps(fake_transcript(truth), indent=1))

    script = "My Test Video\n\n" + "\n\n".join(f"Scene {i+1}:\n{t}" for i, t in enumerate(SCRIPT))
    (out_dir / "script.txt").write_text(script, encoding="utf-8")
    import docx
    doc = docx.Document()
    for i, t in enumerate(SCRIPT):
        doc.add_paragraph(f"Scene {i+1}: {t}")
    doc.save(out_dir / "script.docx")

    m = out_dir / "media"
    make_image(m / "Scene 1.png", "ONE", (40, 70, 140), (1600, 1000))
    make_image(m / "scene_2.jpg", "TWO", (140, 50, 40), (1080, 1350))      # portrait image -> crop to fill
    make_image(m / "3.webp", "THREE", (30, 120, 60), (3000, 1200))         # very wide image
    make_image(m / "Scene 5.png", "FIVE", (110, 40, 130), (800, 450))      # small image -> upscale
    # Scene 4: a short clip WITH sound effects (2.5 s), shorter than the scene.
    ff.run(["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=2.5",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=2.5:sample_rate=48000",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", m / "scene4.mp4"])
    # Background music (two-tone pad) and a whoosh.
    ff.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-f", "lavfi", "-i", "sine=frequency=277:duration=6",
            "-filter_complex", "amix=inputs=2", "-c:a", "libmp3lame", out_dir / "music.mp3"])
    ff.run(["-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.5", "-af", "afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.3",
            out_dir / "whoosh.wav"])
    print(f"Sample created in {out_dir}  (voice length {total:.2f}s, scene starts {starts})")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "sample")
