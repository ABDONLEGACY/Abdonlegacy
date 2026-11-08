"""The "Hand-lettered + underline" [TEXT] style: look, timing, self-drawing underline, auto placement, sounds.

usage:  python tests/make_hand_sample.py HAND_FOLDER PICTURE
        python tests/test_hand_text.py HAND_FOLDER
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FX = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/handfx/sample")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_hand"))
shutil.rmtree(TMP, ignore_errors=True)
os.environ["SCENEFORGE_PROJECTS"] = str(TMP / "projects")
os.environ["SCENEFORGE_SETTINGS"] = str(TMP / "settings")
sys.path.insert(0, str(ROOT))

from sceneforge import effects, paths, pipeline, presets  # noqa: E402
from sceneforge import audio as A  # noqa: E402
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from sceneforge.project import Project  # noqa: E402
from sceneforge.render import Renderer  # noqa: E402

W, H, FPS = 1920, 1080, 30
OUT = TMP / "shots"


def red_mask(f):
    b, g, r = f[..., 0].astype(int), f[..., 1].astype(int), f[..., 2].astype(int)
    return (r > 150) & (r - g > 70) & (r - b > 70)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 1. the new style is the default in every preset
    for name, st in presets.load_all().items():
        assert st["effects"]["text_style"] == "hand_underline", name
    p = Project.create("Hand lettering", "16:9", "Documentary")
    pipeline.save_voice(p, [FX / "voice.wav"])
    pipeline.save_script(p, (FX / "script.txt").read_text(), 2)
    pipeline.run_sync(p, transcript_words=json.loads((FX / "transcript.json").read_text()))
    pipeline.import_media(p, [FX / "media"])
    for kind, f in (("text", "text_pop.wav"), ("underline", "marker_scribble.wav")):
        shutil.copy(FX / f, effects.sounds_dir() / f)
        effects.save_sound_settings(kind, file=f, name=f, volume=1.0)
    truth = {w["w"].strip(): w["s"] for w in json.loads((FX / "truth.json").read_text())["words"]}

    # 2. timing, capitals, tilt, automatic placement
    fx = effects.resolve(p)
    again = effects.resolve(p)
    items = [e for n in sorted(fx) for e in fx[n]]
    for e, e2 in zip(items, [e for n in sorted(again) for e in again[n]]):
        assert (e["x"], e["y"], e["angle"]) == (e2["x"], e2["y"], e2["angle"]), "same result every render"
    for e in items:
        word = e["word"].strip(".,")
        print(f"  [TEXT: {e['text']}] on word '{word}' at {e['t']:.3f}s (spoken {truth[word]:.3f}s), tilt {e['angle']:+.2f} deg,"
              f" auto-placed at {e['x']:.2f} across, {e['y']:.2f} down")
        assert abs(e["t"] - truth[word]) < 0.0015
        assert -4.0 <= e["angle"] <= 2.0 and e["auto"]
    assert len({e["angle"] for e in items}) == len(items), "different tilt on each scene"

    # 3. render the real 1080p video
    r = Renderer(p, quality="standard", size=(W, H), tag="hand")
    out = r.run()

    def frame_at(t):
        raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}", "-i", str(out), "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()

    # the underline is measured against the plain picture (red that the effect added)
    for num, its in fx.items():
        k = r.tl.numbers.index(num)
        plain = r.source(k).src
        for e in its:
            T = e["t"]
            X, Y, _z = plain.project(int(round(T * FPS)) - r.tl.ext[k][0], e["x"], e["y"])
            box = (slice(max(0, int(Y) - 260), int(Y) + 260), slice(max(0, int(X) - 900), int(X) + 900))
            base = red_mask(plain.frame(int(round(T * FPS)) - r.tl.ext[k][0]))[box]

            def line_px(t):
                return int((red_mask(frame_at(t))[box] & ~base).sum())
            t_half = T + effects.LINE_DELAY + effects.LINE_DRAW / 2
            t_done = T + effects.LINE_DELAY + effects.LINE_DRAW + 0.3
            before, start, half, done = line_px(T - 0.1), line_px(T + 0.2), line_px(t_half), line_px(t_done)
            print(f"  {e['text']}: underline red pixels  before word={before}  text appearing={start}  "
                  f"halfway={half} ({half / max(1, done):.0%})  finished={done}")
            assert before < 50 and start < 0.08 * done and 0.3 < half / done < 0.7 and done > 1500
            # faces: the text's real box (where it is drawn on screen) must not overlap any face
            layer = r.source(k).layer
            worst = 0.0
            for t in np.linspace(T + 0.4, min(T + 3.0, r.tl.ext[k][1] / FPS - 0.1), 6):
                kk = int(round(t * FPS)) - r.tl.ext[k][0]
                Xt, Yt, _ = plain.project(kk, e["x"], e["y"])
                L = layer.hand[e["i"]]
                Xt, Yt = layer._keep_inside(Xt, Yt, L["extent"], e["angle"])
                l, tt, rr, bb = effects.rotated_extent(L["extent"], e["angle"])
                assert Xt + l >= W * effects.SAFE - 1 and Xt + rr <= W * (1 - effects.SAFE) + 1, "inside safe margins"
                assert Yt + tt >= H * effects.SAFE - 1 and Yt + bb <= H * (1 - effects.SAFE) + 1, "inside safe margins"
                # the pixels the text really paints: draw only the effect on black and on white frames
                ink = None
                for bg in (0, 255):
                    canvas = np.full((H, W, 3), bg, np.uint8)
                    layer._hand(canvas, e, t - e["t"], *plain.project(kk, e["x"], e["y"])[:2])
                    d = np.abs(canvas.astype(int) - bg).sum(axis=2) > 20
                    ink = d if ink is None else (ink | d)
                for fx_, fy_, fw_, fh_ in effects._faces(plain.frame(kk)):
                    roi = ink[int(fy_):int(fy_ + fh_), int(fx_):int(fx_ + fw_)]
                    worst = max(worst, float(roi.mean()) if roi.size else 0.0)
            print(f"    text vs faces during the scene: largest share of any face covered = {worst:.1%}; inside safe margins")
            assert worst == 0.0
            # sheet: appearing / underline halfway / underline finished
            shots = [(T + 0.12, "text appearing"), (t_half, "underline halfway"), (t_done, "underline finished")]
            row = []
            for t, label in shots:
                f = frame_at(t)
                cv2.rectangle(f, (0, H - 64), (W, H), (0, 0, 0), -1)
                cv2.putText(f, f"[TEXT: {e['text']}] - word '{e['word']}' at {T:.2f}s - {label} ({t:.2f}s)", (20, H - 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.25, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imwrite(str(OUT / f"scene{num}_{label.replace(' ', '_')}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 90])
                row.append(cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA))
            cv2.imwrite(str(OUT / f"scene{num}_sheet.jpg"), np.vstack(row), [cv2.IMWRITE_JPEG_QUALITY, 88])

    # 4. sounds: pop on the word, scribble when the line starts drawing
    fxw = ff.read_audio_f32(r.dir / "fx_track.wav", sr=A.SR, channels=1)[:, 0]
    for e in items:
        for label, t in (("pop", e["t"]), ("scribble", e["t"] + effects.LINE_DELAY)):
            i0 = int((t - 0.1) * A.SR)
            onset = (i0 + int(np.argmax(np.abs(fxw[i0:i0 + int(0.25 * A.SR)]) > 0.01))) / A.SR
            print(f"  {e['text']}: {label} sound starts at {onset:.3f}s (expected {t:.3f}s)")
            assert abs(onset - t) < 0.01

    # 5. the old style is still there
    p.settings["effects"]["text_style"] = "classic"
    p.save()
    r2 = Renderer(p, quality="fast", size=(960, 540), tag="classic")
    assert not r2.source(0).layer.hand and r2.source(0).layer.texts
    shutil.copy(out, TMP / "hand_lettering.mp4")
    r.close()
    r2.close()
    print(f"HAND TEXT TESTS PASSED - pictures in {OUT}")


if __name__ == "__main__":
    main()
