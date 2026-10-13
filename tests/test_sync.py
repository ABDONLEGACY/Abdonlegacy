"""Stage 2 tests: script parsing, voice joining, media matching and scene sync."""
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sceneforge import align, audio, media, script_parser  # noqa: E402

SAMPLE = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/tmp/claude-0/sample")


def test_parse_formats():
    txt = """My title line
**Scene 1:** Hello there [show a map] friend.
More text for one.
SCENE 2 - Second scene here.
## Scene 3
Third.
scene 10. Tenth
"""
    scenes, warns = script_parser.parse_scenes(txt)
    assert [s["number"] for s in scenes] == [1, 2, 3, 10], scenes
    assert scenes[0]["text"] == "Hello there friend. More text for one.", scenes[0]
    assert scenes[1]["text"] == "Second scene here."
    assert any("ignored" in w for w in warns)
    assert any("missing" in w for w in warns)


def test_docx_and_txt():
    for name in ("script.docx", "script.txt"):
        text = script_parser.read_script_file(SAMPLE / name)
        scenes, _ = script_parser.parse_scenes(text)
        assert len(scenes) == 5, (name, scenes)
        assert scenes[0]["text"].startswith("The ancient city")


def test_media_matching():
    files = ["Scene 1.png", "scene_2.mp4", "3.jpg", "scene-10.webp", "Scene 9.mov", "notes.txt", "cover.png",
             "SCENE_004.jpg"]
    mapping, unmatched, _ = media.match_files(files)
    assert mapping == {1: "Scene 1.png", 2: "scene_2.mp4", 3: "3.jpg", 4: "SCENE_004.jpg", 9: "Scene 9.mov",
                       10: "scene-10.webp"}, mapping
    assert unmatched == ["cover.png"]


def test_join_and_sync(tmp="/tmp/claude-0/t_sync"):
    Path(tmp).mkdir(parents=True, exist_ok=True)
    truth = json.loads((SAMPLE / "truth.json").read_text())
    dur = audio.join_voice([SAMPLE / "voice_part1.wav", SAMPLE / "voice_part2.wav"], Path(tmp) / "voice.wav")
    assert abs(dur - truth["duration"]) < 0.05, (dur, truth["duration"])

    scenes, _ = script_parser.parse_scenes(script_parser.read_script_file(SAMPLE / "script.txt"))
    tw = json.loads((SAMPLE / "fake_transcript.json").read_text())
    r1 = align.sync(scenes, tw, dur)
    r2 = align.sync(scenes, tw, dur)
    assert r1 == r2, "sync must be deterministic"
    for res, true_start in zip(r1["scenes"], truth["scene_starts"]):
        print(f"  scene {res['number']}: found {res['start']:.3f}  true {true_start:.3f}  "
              f"conf {res['confidence']}  {res['method']}  {res['flag']}")
        assert abs(res["start"] - true_start) < 0.002, (res, true_start)
        assert not res["flag"], res
    # Caption words keep the script spelling
    texts = [w["text"] for w in r1["words"]]
    assert "nineteen" in texts and "golden" in texts and "single" in texts


def test_flags_unfindable_scene():
    scenes = [{"number": 1, "text": "alpha beta gamma delta epsilon"},
              {"number": 2, "text": "completely different words nobody said here"},
              {"number": 3, "text": "zeta eta theta iota kappa"}]
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa".split()
    tw = [{"w": " " + w, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, w in enumerate(words)]
    r = align.sync(scenes, tw, 6.0)
    s = r["scenes"]
    assert not s[0]["flag"] and not s[2]["flag"]
    assert s[1]["flag"] and "ESTIMATED" in s[1]["flag"], s[1]
    assert s[2]["start"] == 2.5
    assert 0 < s[1]["start"] <= 2.5


def test_long_video_performance():
    """200 scenes, ~30 minutes of speech (~4,500 words) with 8 % transcription errors."""
    rng = random.Random(1)
    vocab = [f"w{i}" for i in range(1500)] + ["the", "a", "of", "and", "to", "in", "is", "it"] * 50
    scenes, tw, starts, t = [], [], [], 0.0
    for n in range(1, 201):
        ws = [rng.choice(vocab) for _ in range(rng.randint(12, 34))]
        scenes.append({"number": n, "text": " ".join(ws)})
        for i, w in enumerate(ws):
            r = rng.random()
            if r < 0.03 and i > 0:
                t += 0.3
                continue  # dropped word
            if r < 0.06:
                w = w + "x"  # misspelt
            elif r < 0.08:
                tw.append({"w": " um", "s": t, "e": t + 0.2}); t += 0.25  # extra word
            if i == 0:
                starts.append(round(t, 3))  # true start = first spoken word of the scene
            tw.append({"w": " " + w, "s": round(t, 3), "e": round(t + 0.3, 3)})
            t += 0.38
        t += 0.4
    t0 = time.time()
    r = align.sync(scenes, tw, t + 1)
    took = time.time() - t0
    errs = [abs(a["start"] - b) for a, b in zip(r["scenes"][1:], starts[1:]) if not a["flag"]]
    flagged = sum(1 for a in r["scenes"] if a["flag"])
    wrong = sum(1 for e in errs if e > 0.05)
    for a, b in zip(r["scenes"], starts):
        if not a["flag"] and abs(a["start"] - b) > 0.05:
            print("   WRONG", a, b)
    print(f"  200 scenes / {len(tw)} words / {t/60:.1f} min aligned in {took:.2f}s; flagged {flagged}; "
          f"unflagged-but-wrong {wrong}")
    assert took < 30
    assert wrong == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(name)
            fn()
    print("ALL SYNC TESTS PASSED")
