"""Small helpers around the ffmpeg / ffprobe command-line tools."""
import json
import subprocess

from . import paths

# Stop a black console window flashing up for every ffmpeg call on Windows.
_CREATE_FLAGS = 0x08000000 if paths.IS_WINDOWS else 0  # CREATE_NO_WINDOW


class FFmpegError(RuntimeError):
    pass


def run(args, desc="ffmpeg"):
    """Run ffmpeg with the given arguments, raising a readable error on failure."""
    cmd = [paths.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"] + [str(a) for a in args]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_CREATE_FLAGS)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()[-2000:]
        raise FFmpegError(f"{desc} failed:\n{err}")
    return proc


def run_to(args, out_path, desc="ffmpeg"):
    """Run ffmpeg writing to a temporary file, then swap it into place (safe if Windows has the old file
    locked for a moment, and never leaves a half-written file behind)."""
    import os
    from pathlib import Path
    out_path = Path(out_path)
    tmp = out_path.with_name(f"{out_path.stem}.part{os.getpid()}{out_path.suffix}")
    try:
        run(list(args) + [str(tmp)], desc=desc)
        paths.safe_replace(tmp, out_path)
    finally:
        paths.safe_unlink(tmp, tries=1)
    return out_path


def popen(args, stdin=None, stdout=None):
    """Start ffmpeg in the background. Its messages are read continuously by a helper thread: on Windows a
    pipe only holds a few kilobytes, and an unread message pipe would make ffmpeg (and SceneForge) wait
    for each other forever."""
    import threading
    cmd = [paths.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"] + [str(a) for a in args]
    proc = subprocess.Popen(cmd, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                            creationflags=_CREATE_FLAGS)
    tail = bytearray()
    proc.err_tail = tail
    pipe = proc.stderr

    def drain():
        try:
            for chunk in iter(lambda: pipe.read(4096), b""):
                tail.extend(chunk)
                del tail[:-8000]
        except Exception:
            pass

    proc.err_thread = threading.Thread(target=drain, daemon=True)
    proc.err_thread.start()
    return proc


def stderr_text(proc):
    """The last messages an ffmpeg started with popen() wrote."""
    t = getattr(proc, "err_thread", None)
    if t is not None:
        t.join(timeout=2)
    return bytes(getattr(proc, "err_tail", b"")).decode("utf-8", "replace")[-1500:]


def probe(path):
    cmd = [paths.ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_CREATE_FLAGS)
    if proc.returncode != 0:
        raise FFmpegError(f"Could not read file {path}:\n{proc.stderr.decode('utf-8', 'replace')[-800:]}")
    return json.loads(proc.stdout.decode("utf-8", "replace"))


def duration(path):
    info = probe(path)
    d = info.get("format", {}).get("duration")
    if d is None:
        for s in info.get("streams", []):
            if s.get("duration"):
                d = s["duration"]
                break
    return float(d or 0.0)


def video_info(path):
    """Return dict(width, height, duration, has_audio, fps) for a video file."""
    info = probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v is None:
        raise FFmpegError(f"{path} has no video stream")
    dur = float(v.get("duration") or info.get("format", {}).get("duration") or 0)
    fps = 30.0
    try:
        n, d = v.get("avg_frame_rate", "30/1").split("/")
        fps = float(n) / float(d) if float(d) else 30.0
    except Exception:
        pass
    return {"width": int(v.get("width", 0)), "height": int(v.get("height", 0)),
            "duration": dur, "has_audio": a is not None, "fps": fps or 30.0}


def read_audio_f32(path, sr=48000, channels=2, start=None, duration_s=None, filters=None):
    """Decode audio into float32 numpy array of shape (samples, channels)."""
    import numpy as np
    args = []
    if start:
        args += ["-ss", f"{start:.6f}"]
    args += ["-i", str(path)]
    if duration_s is not None:
        args += ["-t", f"{duration_s:.6f}"]
    args += ["-vn"]
    if filters:
        args += ["-af", filters]
    args += ["-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    proc = run(args, desc="audio decode")
    data = np.frombuffer(proc.stdout, dtype=np.float32)
    return data.reshape(-1, channels).copy()
