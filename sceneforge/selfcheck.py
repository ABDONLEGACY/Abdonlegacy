"""Quick health check: tools found, a tiny video renders. Run:  python -m sceneforge.selfcheck"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


def main():
    ok = True
    print("SceneForge self-check")
    print(f"  Python {sys.version.split()[0]}")
    try:
        from sceneforge import ffmpeg_utils as ff, paths
        print(f"  FFmpeg: {paths.ffmpeg()}")
    except Exception as e:  # noqa: BLE001
        print(f"  PROBLEM: {e}")
        return 1
    for mod in ("fastapi", "uvicorn", "multipart", "faster_whisper", "cv2", "numpy", "PIL", "rapidfuzz", "docx"):
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001
            print(f"  PROBLEM: cannot load {mod}: {e}")
            ok = False
    if not ok:
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="sceneforge_check_"))
    os.environ["SCENEFORGE_PROJECTS"] = str(tmp / "projects")
    try:
        import numpy as np
        from PIL import Image
        from sceneforge import pipeline
        from sceneforge.project import Project
        from sceneforge.render import Renderer
        ff.run(["-f", "lavfi", "-i", "sine=frequency=300:duration=4", str(tmp / "voice.wav")])
        for i, c in enumerate([(200, 60, 60), (60, 120, 200)]):
            Image.fromarray(np.full((360, 640, 3), c, np.uint8)).save(tmp / f"scene {i + 1}.png")
        p = Project.create("Self check", "16:9", "Animated Explainer")
        pipeline.save_voice(p, [tmp / "voice.wav"])
        pipeline.save_script(p, "Scene 1: hello there world\nScene 2: second part here", 2)
        words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, w in
                 enumerate("hello there world second part here".split())]
        pipeline.run_sync(p, transcript_words=words)
        pipeline.import_media(p, [tmp / "scene 1.png", tmp / "scene 2.png"])
        t = time.time()
        out = Renderer(p, quality="fast", size=(640, 360)).run()
        frames = round(ff.duration(out) * 30)
        print(f"  Test video rendered in {time.time() - t:.1f}s ({frames} frames)")
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"  PROBLEM: test render failed: {e}")
        ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ALL GOOD" if ok else "  SELF-CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
