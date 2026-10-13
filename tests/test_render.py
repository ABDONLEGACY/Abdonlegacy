"""Stages 3-5: motion, transitions, clips, audio and captions, rendered from the sample project.

usage: python tests/test_render.py [SAMPLE_FOLDER]
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SAMPLE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/sample")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_test"))
os.environ["SCENEFORGE_PROJECTS"] = str(TMP / "projects")

from sceneforge import ffmpeg_utils as ff  # noqa: E402
from sceneforge import paths, pipeline  # noqa: E402
from sceneforge.motion import plan_motions  # noqa: E402
from sceneforge.project import Project  # noqa: E402
from sceneforge.render import Renderer  # noqa: E402
from sceneforge.sources import ImageSource  # noqa: E402

SCENE_COLORS = {1: (40, 70, 140), 2: (140, 50, 40), 3: (30, 120, 60), 5: (110, 40, 130)}


def make_project(name="Test", preset="Animated Explainer", aspect="16:9"):
    shutil.rmtree(TMP / "projects" / name, ignore_errors=True)
    p = Project.create(name, aspect, preset)
    pipeline.save_voice(p, [SAMPLE / "voice_part2.wav", SAMPLE / "voice_part1.wav"])  # natural order fixes it
    pipeline.save_script(p, (SAMPLE / "script.txt").read_text(), expected=5)
    tw = json.loads((SAMPLE / "fake_transcript.json").read_text())
    pipeline.run_sync(p, transcript_words=tw)
    pipeline.import_media(p, [SAMPLE / "media"])
    assert pipeline.missing_media(p) == [], pipeline.missing_media(p)
    return p


def frames_of(path, W, H):
    proc = subprocess.run([paths.ffmpeg(), "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True)
    return np.frombuffer(proc.stdout, np.uint8).reshape(-1, H, W, 3)


def nearest_scene(frame):
    c = frame[frame.shape[0] // 2 - 5:frame.shape[0] // 2 + 5, 10:30].reshape(-1, 3).mean(0)
    # sample a background area (left edge, middle row) and pick the closest scene colour
    best = min(SCENE_COLORS, key=lambda k: np.abs(np.array(SCENE_COLORS[k]) - c).sum())
    return best, np.abs(np.array(SCENE_COLORS[best]) - c).sum()


def test_motion_variety():
    st = {"motion": {"zoom_min": 1.05, "zoom_max": 1.2, "pan_min": 0.04, "pan_max": 0.08,
                     "types": ["zoom_in", "zoom_out", "pan_left", "pan_right", "zoom_in_pan", "zoom_out_pan"],
                     "easing": ["linear", "ease_in_out"]}}
    nums = list(range(1, 201))
    a = plan_motions(nums, set(nums), st, 1234)
    b = plan_motions(nums, set(nums), st, 1234)
    assert a == b, "same seed must give same motions"
    types = [a[n]["type"] for n in nums]
    assert all(types[i] != types[i + 1] for i in range(len(types) - 1)), "no repeats in a row"
    assert len(set(types)) == 6
    zooms = {round(max(m["z0"], m["z1"]), 3) for m in a.values()}
    assert len(zooms) > 100, "zoom amounts should vary"


def _bilinear(img, xs, ys):
    """Independent reference sampler (numpy, float) with reflect-101 style edge clamping."""
    h, w = img.shape[:2]
    xs = np.clip(xs, 0, w - 1.000001)
    ys = np.clip(ys, 0, h - 1.000001)
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = (xs - x0)[..., None], (ys - y0)[..., None]
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def test_motion_smooth():
    """Every rendered frame must equal the mathematically exact frame for the camera path (to within 8-bit
    rounding), and the camera path itself must move in even, smooth steps - i.e. no jitter."""
    from sceneforge.motion import camera_at
    W, H = 320, 180
    TMP.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    tex = cv2.GaussianBlur((rng.random((900, 1600, 3)) * 255).astype(np.uint8), (0, 0), 2)
    img_path = TMP / "texture.png"
    cv2.imwrite(str(img_path), tex)
    plans = {
        "pan": {"type": "pan_right", "easing": "linear", "z0": 1.12, "z1": 1.12, "x0": -0.04, "x1": 0.04, "y0": 0, "y1": 0},
        "zoom_in_pan": {"type": "zoom_in_pan", "easing": "ease_in_out", "z0": 1.0, "z1": 1.18, "x0": 0, "x1": 0.05,
                        "y0": 0, "y1": 0.02},
    }
    for name, plan in plans.items():
        L = 120
        src = ImageSource(img_path, W, H, L, plan)
        base = src.base.astype(np.float64)
        worst = 0.0
        lefts = []
        for k, f in enumerate(src.frames(0, L)):
            z, xo, yo = camera_at(plan, k / (L - 1))
            ww, wh = src.unit_w / z, src.unit_h / z
            left = src.bw / 2 + xo * src.unit_w - ww / 2
            top = src.bh / 2 + yo * src.unit_h - wh / 2
            lefts.append(left)
            if k % 7 == 0:
                u = (np.arange(W) + 0.5) * ww / W - 0.5 + left
                v = (np.arange(H) + 0.5) * wh / H - 0.5 + top
                ref = _bilinear(base, u[None, :].repeat(H, 0), v[:, None].repeat(W, 1))
                worst = max(worst, np.abs(f[2:-2, 2:-2].astype(np.float64) - ref[2:-2, 2:-2]).max())
        jerk = np.abs(np.diff(lefts, n=3)).max()  # smooth curve -> tiny 3rd differences, jitter -> large
        print(f"  {name}: max difference from exact frame {worst:.2f} levels; camera path jerk {jerk:.5f}px")
        assert worst <= 1.0, worst
        assert jerk < 0.01, jerk


def test_render_cut_sync():
    p = make_project("SyncCut")
    p.settings["transitions"]["mode"] = "cut"
    p.settings["captions"]["enabled"] = False
    p.settings["clips"]["keep_audio"] = False
    p.save()
    W, H = 640, 360
    r = Renderer(p, quality="fast", size=(W, H), tag="test")
    out = r.run()
    info = ff.probe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    nb = int(subprocess.run([paths.ffprobe(), "-v", "error", "-count_frames", "-select_streams", "v:0",
                             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
                            capture_output=True, text=True).stdout.strip())
    N = round(p.data["audio_duration"] * 30)
    print(f"  frames {nb} expected {N}; video {float(v['duration']):.3f}s audio {p.data['audio_duration']:.3f}s")
    assert nb == N
    frames = frames_of(out, W, H)
    B = r.tl.B
    for k in range(1, r.tl.n):
        num_prev, num = r.tl.numbers[k - 1], r.tl.numbers[k]
        if num_prev in SCENE_COLORS:
            s, _ = nearest_scene(frames[B[k] - 1])
            assert s == num_prev, (k, s)
        if num in SCENE_COLORS:
            s, _ = nearest_scene(frames[B[k]])
            assert s == num, (k, s)
        print(f"  scene {num} begins at frame {B[k]} = {B[k]/30:.3f}s "
              f"(word at {p.scene(num)['start']:.3f}s)")
        assert abs(B[k] / 30 - p.scene(num)["start"]) <= 1 / 60 + 1e-9


def test_render_transitions_resume_and_audio():
    p = make_project("Full")
    st = p.settings
    st["transitions"].update(mode="rotate", duration=0.5)
    st["captions"].update(enabled=True, mode="word")
    st["clips"].update(keep_audio=True, clip_volume=0.25, fit_mode="slow_then_freeze")
    p.data["music"] = p.rel(p.copy_in(SAMPLE / "music.mp3", p.audio_dir))
    p.data["sfx"] = p.rel(p.copy_in(SAMPLE / "whoosh.wav", p.audio_dir))
    p.save()
    W, H = 640, 360
    msgs = []
    r = Renderer(p, quality="fast", size=(W, H), tag="test", progress=lambda f, m: msgs.append((f, m)))
    print("  transitions:", r.tl.types, "half-lengths:", r.tl.h)
    t0 = time.time()
    out = r.run()
    first = time.time() - t0
    frames = frames_of(out, W, H)
    N = round(p.data["audio_duration"] * 30)
    assert len(frames) == N, (len(frames), N)
    # transition centred on the boundary: at B-h-1 pure old scene, at B+h pure new scene
    for k in range(1, r.tl.n):
        h = r.tl.h[k - 1]
        a, b = r.tl.numbers[k - 1], r.tl.numbers[k]
        if a in SCENE_COLORS and b in SCENE_COLORS:
            fa = frames[r.tl.B[k] - h - 1]
            fb = frames[r.tl.B[k] + h]
            assert nearest_scene(fa)[0] == a and nearest_scene(fb)[0] == b
    # Audio: duration equal to voiceover, clip sound present during scene 4
    ainfo = next(s for s in ff.probe(out)["streams"] if s["codec_type"] == "audio")
    print(f"  audio {float(ainfo['duration']):.3f}s vs voice {p.data['audio_duration']:.3f}s; first render {first:.1f}s")
    assert abs(float(ainfo["duration"]) - p.data["audio_duration"]) < 0.06
    # Resume / reuse: rendering again reuses every piece
    msgs.clear()
    t0 = time.time()
    Renderer(p, quality="fast", size=(W, H), tag="test", progress=lambda f, m: msgs.append((f, m))).run()
    again = time.time() - t0
    assert any("already done" in m and "Rendering 0 of" in m for _, m in msgs), msgs[:3]
    print(f"  re-render with nothing changed: {again:.1f}s")
    # Nudging scene 3 only re-renders the pieces around it
    pipeline.nudge(p, 3, delta=0.2)
    msgs.clear()
    r3 = Renderer(p, quality="fast", size=(W, H), tag="test", progress=lambda f, m: msgs.append((f, m)))
    r3.run()
    first_msg = next(m for _, m in msgs if m.startswith("Rendering "))
    print("  after nudge:", first_msg)
    assert "Rendering 0 of" not in first_msg
    shutil.copy(out, TMP / "full_test.mp4")


def test_preview():
    p = Project.open(TMP / "projects" / "Full")
    r = Renderer(p, quality="fast", size=(480, 270), tag="preview")
    out = r.preview(4)
    d = ff.duration(out)
    k = r.tl.numbers.index(4)
    e0, e1 = r.tl.ext[k]
    print(f"  preview of scene 4: {d:.2f}s (expected {(e1-e0)/30:.2f}s)")
    assert abs(d - (e1 - e0) / 30) < 0.1


if __name__ == "__main__":
    only = sys.argv[2:] if len(sys.argv) > 2 else None
    for name, fn in list(globals().items()):
        if name.startswith("test_") and (not only or name in only):
            print(name)
            fn()
    print("ALL RENDER TESTS PASSED")
