"""Scene Effects: markers, timing on the exact word, pins locked to the moving picture, sounds, rendering.

usage:  python tests/make_effects_sample.py FX_FOLDER
        python tests/test_effects.py FX_FOLDER
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
FX = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/fxs")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_fx"))
shutil.rmtree(TMP, ignore_errors=True)
os.environ["SCENEFORGE_PROJECTS"] = str(TMP / "projects")
os.environ["SCENEFORGE_SETTINGS"] = str(TMP / "settings")
sys.path.insert(0, str(ROOT))

from sceneforge import effects, paths, pipeline, script_parser  # noqa: E402
from sceneforge import audio as A  # noqa: E402
from sceneforge import ffmpeg_utils as ff  # noqa: E402
from sceneforge.project import Project  # noqa: E402
from sceneforge.render import Renderer  # noqa: E402
from sceneforge.sources import ImageSource  # noqa: E402

W, H, FPS = 960, 540, 30
OUT = TMP / "shots"


def setup_project():
    truth = json.loads((FX / "truth.json").read_text())
    p = Project.create("Effects demo", "16:9", "Documentary")
    pipeline.save_voice(p, [FX / "voice.wav"])
    pipeline.save_script(p, (FX / "script.txt").read_text(), 3)
    pipeline.run_sync(p, transcript_words=json.loads((FX / "transcript.json").read_text()))
    pipeline.import_media(p, [FX / "media"])
    # place the pins on the cities, as you would by clicking in the Effects window
    for e in p.scene(1)["effects"]:
        e["x"], e["y"] = truth["cities"][e["text"]]
        e["placed"] = True
    p.settings["captions"]["enabled"] = True
    p.save()
    # sounds, uploaded once in Settings
    for kind, name in (("pin", "pin_drop.wav"), ("text", "text_pop.wav")):
        shutil.copy(FX / name, effects.sounds_dir() / name)
        effects.save_sound_settings(kind, file=name, name=name, volume=0.9)
    return p, truth


def test_markers_never_reach_sync_or_captions(p, truth):
    plain = [{"number": s["number"], "text": script_parser.EFFECT_RE.sub(" ", s["text"])} for s in p.scenes]
    assert [s["text"] for s in plain] == [s["text"] for s in p.scenes]
    for s in p.scenes:
        assert "[" not in s["text"] and "PIN" not in s["text"].upper().split(), s["text"]
    words = p.words()
    assert not any("[" in w["text"] or w["text"].upper().startswith(("PIN", "TEXT")) for w in words)
    starts = [s["start"] for s in p.scenes]
    print(f"  scene starts {starts} (true {truth['scene_starts']}) - markers don't change timing")
    for got, true in zip(starts[1:], truth["scene_starts"][1:]):
        assert abs(got - true) < 0.002


def test_effects_land_on_their_word(p, truth):
    fx = effects.resolve(p)
    true_t = {w["w"].strip(): w["s"] for w in truth["words"]}
    got = [(n, e["type"], e["text"], e["word"], e["t"]) for n, items in fx.items() for e in items]
    for n, kind, text, word, t in got:
        key = word.strip(".,")
        print(f"  scene {n}: {kind:4s} {text!r:12s} on word {word!r:12s} at {t:.3f}s (spoken at {true_t[key]:.3f}s)")
        assert abs(t - true_t[key]) < 0.0015
    assert [g[3].strip(".,") for g in got] == ["Rome", "Carthage", "1940"]
    return fx


def test_pins_locked_to_picture(p, truth):
    """The pin's tip must sit on the city dot in every frame, while the camera zooms and pans."""
    for plan in (None, {"type": "zoom_in_pan", "easing": "ease_in_out", "z0": 1.0, "z1": 1.2, "x0": 0, "y0": 0,
                        "x1": 0.06, "y1": -0.03}):
        _check_lock(p, truth, plan)


def _check_lock(p, truth, plan):
    r = Renderer(p, quality="fast", size=(W, H), tag="fxtest")
    k = r.tl.numbers.index(1)
    if plan:
        r.tl.motions[1] = plan
    src = r.source(k).src  # the plain image source underneath the effects
    assert isinstance(src, ImageSource)
    print(f"  scene 1 camera move: {r.tl.motions[1]['type']} zoom {r.tl.motions[1]['z0']}->{r.tl.motions[1]['z1']}")
    worst = 0.0
    for kk in range(0, r.tl.ext[k][1] - r.tl.ext[k][0], 9):
        frame = src.frame(kk)
        mask = (frame[:, :, 0] > 200) & (frame[:, :, 1] < 60) & (frame[:, :, 2] > 200)  # magenta dots (BGR)
        n, lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
        for name, (fx, fy) in truth["cities"].items():
            X, Y, _z = src.project(kk, fx, fy)
            if not (0 < X < W and 0 < Y < H):
                continue
            # nearest detected dot centre (pixel centres -> edge coordinates: +0.5)
            d = min(np.hypot(cx + 0.5 - X, cy + 0.5 - Y) for cx, cy in cents[1:])
            worst = max(worst, d)
    print(f"  pin anchor vs city dot on the moving map: worst distance {worst:.2f} px")
    assert worst < 0.75, worst
    r.close()


def test_render_and_sound(p, fx):
    r = Renderer(p, quality="fast", size=(W, H), tag="fxtest")
    out = r.run()
    n = int(subprocess.run([paths.ffprobe(), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout)
    assert n == r.tl.N, (n, r.tl.N)
    frames = np.frombuffer(subprocess.run([paths.ffmpeg(), "-v", "error", "-i", str(out), "-f", "rawvideo",
                                           "-pix_fmt", "bgr24", "-"], capture_output=True).stdout,
                           np.uint8).reshape(-1, H, W, 3)
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = []
    red = lambda f: (f[:, :, 2] > 170) & (f[:, :, 1] < 90) & (f[:, :, 0] < 90)  # noqa: E731
    for num, items in fx.items():
        k = r.tl.numbers.index(num)
        src = r.source(k)
        for e in items:
            T = e["t"]
            g = int(round(T * FPS))
            local = g - r.tl.ext[k][0]
            X, Y, z = src.src.project(local, e["x"], e["y"])
            if e["type"] == "pin":
                # before the drop: no pin near the city; on the word: pin tip on the city
                box = lambda f: red(f)[max(0, int(Y) - 70):int(Y) + 4, max(0, int(X) - 30):int(X) + 30]  # noqa: E731
                before = box(frames[g - int(0.5 * FPS)]).sum()
                landed = box(frames[g]).sum()
                after = box(frames[g + FPS]).sum()
                print(f"  pin {e['text']}: red pixels at the city 0.5s before={before}, on the word={landed}, 1s after={after}")
                assert before < 20 and landed > 200 and after > 200
            else:
                c = frames[g - 2][int(Y) - 20:int(Y) + 20, int(X) - 60:int(X) + 60]
                d = frames[g + 10][int(Y) - 20:int(Y) + 20, int(X) - 60:int(X) + 60]
                white_before, white_after = int((c.min(axis=2) > 235).sum()), int((d.min(axis=2) > 235).sum())
                print(f"  text {e['text']}: white text pixels just before the word={white_before}, 1/3 s after={white_after}")
                assert white_after > 300 and white_after > 5 * (white_before + 1)
            picks = [(-0.20, "falling"), (0.0, "ON THE WORD"), (0.15, "bounce"), (1.0, "+1 s")] if e["type"] == "pin" \
                else [(-0.1, "before"), (0.0, "ON THE WORD"), (0.12, "popping"), (1.0, "+1 s")]
            row = []
            for dt, label in picks:
                f = frames[int(round((T + dt) * FPS))].copy()
                cv2.rectangle(f, (0, 0), (W, 34), (0, 0, 0), -1)
                cv2.putText(f, f"{e['type'].upper()} {e['text']} - word '{e['word']}' at {T:.2f}s - {label} "
                               f"({T + dt:.2f}s)", (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
                row.append(cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA))
            sheets.append(np.hstack(row))
            cv2.imwrite(str(OUT / f"effect_{num}_{e['i']}_{e['type']}.png"), np.vstack([np.hstack(row[:2]), np.hstack(row[2:])]))
    cv2.imwrite(str(OUT / "all_effects.png"), np.vstack(sheets))
    # sounds: the effects track must start each sound exactly on its word
    fxw = ff.read_audio_f32(r.dir / "fx_track.wav", sr=A.SR, channels=1)[:, 0]
    for items in fx.values():
        for e in items:
            i0 = int((e["t"] - 0.2) * A.SR)
            seg = np.abs(fxw[i0:i0 + int(0.4 * A.SR)])
            onset = (i0 + int(np.argmax(seg > 0.02))) / A.SR
            print(f"  {e['type']} sound starts at {onset:.3f}s (word at {e['t']:.3f}s)")
            assert abs(onset - e["t"]) < 0.005
    # the plain scene (3) took the normal path
    assert type(r.source(r.tl.numbers.index(3))).__name__ == "ImageSource"
    shutil.copy(out, TMP / "effects_demo.mp4")
    r.close()


if __name__ == "__main__":
    p, truth = setup_project()
    print("test_markers_never_reach_sync_or_captions")
    test_markers_never_reach_sync_or_captions(p, truth)
    print("test_effects_land_on_their_word")
    fx = test_effects_land_on_their_word(p, truth)
    print("test_pins_locked_to_picture")
    test_pins_locked_to_picture(p, truth)
    print("test_render_and_sound")
    test_render_and_sound(p, fx)
    print(f"EFFECTS TESTS PASSED - pictures in {OUT}")
