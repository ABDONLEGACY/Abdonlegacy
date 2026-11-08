"""Windows sometimes keeps a file locked for a moment (OneDrive syncing, antivirus scanning, a video player).
Saving must wait and retry instead of failing. On Linux we simulate the lock: the first attempts to replace
a file raise PermissionError, exactly like Windows ("Access is denied").

usage: python tests/test_windows_locks.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sf_locks_"))
os.environ["SCENEFORGE_PROJECTS"] = str(TMP / "projects")
os.environ["SCENEFORGE_SETTINGS"] = str(TMP / "settings")
sys.path.insert(0, str(ROOT))

from sceneforge import ffmpeg_utils as ff, paths, presets  # noqa: E402
from sceneforge.project import Project  # noqa: E402

_real_replace = Path.replace
LOCKED = {"left": 0}


def flaky_replace(self, target):
    if LOCKED["left"] > 0:
        LOCKED["left"] -= 1
        raise PermissionError(13, "Access is denied (simulated Windows lock)", str(target))
    return _real_replace(self, target)


def main():
    Path.replace = flaky_replace
    try:
        # project.json save: locked 5 times, then free
        p = Project.create("Locked", "16:9", "Documentary")
        LOCKED["left"] = 5
        p.data["settings"]["captions"]["enabled"] = False
        p.save()
        assert Project.open(p.dir).settings["captions"]["enabled"] is False
        print("  project save waited out a 5x lock")
        # presets file
        LOCKED["left"] = 5
        presets.save("Documentary", presets.get("Documentary"))
        print("  preset save waited out a 5x lock")
        # an ffmpeg output that is overwritten every render
        out = TMP / "audio.m4a"
        ff.run(["-f", "lavfi", "-i", "sine=duration=1", str(out)])
        LOCKED["left"] = 5
        ff.run_to(["-f", "lavfi", "-i", "sine=duration=2"], out)
        assert abs(ff.duration(out) - 2.0) < 0.1
        assert not list(TMP.glob("audio.part*"))
        print("  render output replaced after a 5x lock, no leftovers")
        # a lock that never goes away gives a clear error (not a silent failure)
        LOCKED["left"] = 10_000
        try:
            p.save()
            raise SystemExit("expected an error")
        except PermissionError:
            print("  a permanent lock is reported as an error")
        LOCKED["left"] = 0
        # the server turns it into a readable message
        from fastapi.testclient import TestClient
        from sceneforge.server import app
        c = TestClient(app, raise_server_exceptions=False)
        LOCKED["left"] = 10_000
        r = c.patch("/api/projects/Locked", json={"name": "Locked 2"})
        LOCKED["left"] = 0
        print("  server message:", r.status_code, r.json()["error"][:90], "...")
        assert r.status_code == 500 and "another program" in r.json()["error"]
        assert (paths.APP_DIR / "sceneforge_problems.log").exists()
    finally:
        Path.replace = _real_replace
        shutil.rmtree(TMP, ignore_errors=True)
    print("WINDOWS LOCK TESTS PASSED")


if __name__ == "__main__":
    main()
