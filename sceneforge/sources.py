"""Frame sources: produce the frames of one scene (image with motion, or video clip fitted to length).

Frame indices are local to the scene's *extended* range (scene length plus the transition overlap
on each side), so motion keeps going smoothly through the transitions.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import ffmpeg_utils as ff
from .motion import camera_at

INTERP = cv2.INTER_LINEAR


def warp_exact(src_f32, M, W, H):
    """Sub-pixel exact warp. FFmpeg's zoompan snaps to whole pixels (jitter) and OpenCV's 8-bit warp snaps
    to 1/32 pixel; warping float data has no position rounding at all, so slow pans and zooms are perfectly
    smooth. Output equals the exact frame to within rounding of the final 8-bit values."""
    out = cv2.warpAffine(src_f32, M, (W, H), flags=INTERP | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
    return cv2.convertScaleAbs(out)


def load_image_rgb(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img)
    return np.asarray(img.convert("RGB"))


def cover_resize(arr, w, h, interp_up=cv2.INTER_CUBIC):
    """Scale an array so it covers w x h (keeping its shape), then centre-crop to exactly w x h."""
    ih, iw = arr.shape[:2]
    s = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * s))), max(h, int(round(ih * s)))
    interp = cv2.INTER_AREA if s < 1 else interp_up
    arr = cv2.resize(arr, (nw, nh), interpolation=interp)
    x, y = (nw - w) // 2, (nh - h) // 2
    return arr[y:y + h, x:x + w]


class ImageSource:
    """A still image with a smooth sub-pixel camera move (no zoompan jitter: we warp with float precision)."""

    def __init__(self, path, W, H, length, plan):
        self.W, self.H, self.length, self.plan = W, H, max(1, length), plan
        zb = max(plan["z0"], plan["z1"], 1.0)
        rgb = load_image_rgb(path)
        ih, iw = rgb.shape[:2]
        # Base picture: big enough that the most zoomed-in view is still at full resolution.
        s = max(W * zb / iw, H * zb / ih)
        # round UP so the picture is never even a fraction of a pixel smaller than the widest view
        bw, bh = max(1, int(np.ceil(iw * s - 1e-6))), max(1, int(np.ceil(ih * s - 1e-6)))
        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LANCZOS4
        base = cv2.resize(rgb, (bw, bh), interpolation=interp)[:, :, ::-1]  # BGR
        self.base = np.ascontiguousarray(base, dtype=np.float32)
        self.bw, self.bh = bw, bh
        self.unit_w, self.unit_h = W * zb, H * zb  # size of the full frame (zoom 1.0) in base pixels

    def frame(self, k):
        p = k / (self.length - 1) if self.length > 1 else 0.0
        z, xo, yo = camera_at(self.plan, p)
        ww, wh = self.unit_w / z, self.unit_h / z
        cx = self.bw / 2 + xo * self.unit_w
        cy = self.bh / 2 + yo * self.unit_h
        # keep the window inside the picture (safety; valid plans never hit this)
        cx = min(max(cx, ww / 2), self.bw - ww / 2) if ww < self.bw else self.bw / 2
        cy = min(max(cy, wh / 2), self.bh - wh / 2) if wh < self.bh else self.bh / 2
        sx, sy = ww / self.W, wh / self.H
        x0 = cx - ww / 2 + 0.5 * sx - 0.5
        y0 = cy - wh / 2 + 0.5 * sy - 0.5
        M = np.array([[sx, 0, x0], [0, sy, y0]], dtype=np.float64)
        return warp_exact(self.base, M, self.W, self.H)

    def frames(self, a, b):
        for k in range(a, b):
            yield self.frame(k)

    def close(self):
        self.base = None


def clip_fit(duration, length, fps, fit_mode, max_slowdown):
    """Decide how a clip of `duration` seconds fills `length` frames.

    Returns dict(speed, real_frames, fill) where fill is "" | "freeze" | "loop".
    """
    have = duration * fps
    if have >= length - 0.5:
        return {"speed": 1.0, "real_frames": length, "fill": ""}
    need_ratio = length / max(have, 1e-6)
    if fit_mode.startswith("slow_then") and need_ratio <= 1.0 + max_slowdown + 1e-6:
        return {"speed": round(1.0 / need_ratio, 6), "real_frames": length, "fill": ""}
    fill = "loop" if fit_mode.endswith("loop") else "freeze"
    return {"speed": 1.0, "real_frames": max(1, int(have)), "fill": fill}


class VideoSource:
    """A video clip scaled/cropped to fill the frame and fitted to the scene length."""

    LOOP_SECONDS = 1.5

    def __init__(self, path, W, H, fps, length, work_dir, fit_mode, max_slowdown):
        self.path, self.W, self.H, self.fps, self.length = Path(path), W, H, fps, max(1, length)
        self.info = ff.video_info(path)
        self.fit = clip_fit(self.info["duration"], self.length, fps, fit_mode, max_slowdown)
        st = self.path.stat()
        key = json.dumps([str(self.path), st.st_size, int(st.st_mtime), W, H, fps, self.fit], sort_keys=True)
        self.key = hashlib.sha1(key.encode()).hexdigest()[:12]
        self.dir = Path(work_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.conform = self.dir / f"clip_{self.key}.mp4"
        self.L = self.fit["real_frames"]
        self._last = None
        self._tail_mm = None
        self._prepare()

    def _prepare(self):
        if self.conform.exists():
            return
        tmp = self.dir / f"clip_{self.key}.part.mp4"
        slow = 1.0 / self.fit["speed"]
        vf = (f"setpts={slow:.6f}*(PTS-STARTPTS),fps={self.fps},"
              f"scale={self.W}:{self.H}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={self.W}:{self.H},setsar=1,"
              f"tpad=stop_mode=clone:stop=2,trim=end_frame={self.L},"
              f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p")
        ff.run(["-i", str(self.path), "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "12",
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-f", "mp4", str(tmp)], desc=f"Preparing clip {self.path.name}")
        tmp.replace(self.conform)

    def _decode(self, a, b):
        """Yield real frames a..b-1 (0 <= a < b <= L) as BGR arrays."""
        proc = ff.popen(["-i", str(self.conform), "-vf", f"trim=start_frame={a}:end_frame={b},scale=in_color_matrix=bt709:in_range=tv,format=bgr24",
                         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        size = self.W * self.H * 3
        got = 0
        last = None
        try:
            while got < b - a:
                buf = proc.stdout.read(size)
                if len(buf) < size:
                    break
                last = np.frombuffer(buf, dtype=np.uint8).reshape(self.H, self.W, 3)
                got += 1
                yield last
        finally:
            proc.stdout.close()
            proc.wait()
        # Decoder delivered fewer frames than promised (rounding): repeat the last one.
        while got < b - a and last is not None:
            got += 1
            yield last

    def _last_frame(self):
        if self._last is None:
            for f in self._decode(self.L - 1, self.L):
                self._last = f.astype(np.float32)
        return self._last

    def _load_tail(self, P):
        """Keep the last P real frames in a memory-mapped file on disk (cheap on RAM, even for 4K)."""
        if self._tail_mm is not None:
            return self._tail_mm
        f = self.dir / f"clip_{self.key}_tail{P}.npy"
        if f.exists():
            try:
                self._tail_mm = np.load(f, mmap_mode="r")
                return self._tail_mm
            except Exception:
                f.unlink(missing_ok=True)
        tmp = self.dir / f"clip_{self.key}_tail{P}.part.npy"
        mm = np.lib.format.open_memmap(str(tmp), mode="w+", dtype=np.uint8, shape=(P, self.H, self.W, 3))
        for i, fr in enumerate(self._decode(self.L - P, self.L)):
            mm[i] = fr
        mm.flush()
        del mm
        tmp.replace(f)
        self._tail_mm = np.load(f, mmap_mode="r")
        return self._tail_mm

    def frames(self, a, b):
        L = self.L
        if a < L:
            yield from self._decode(a, min(b, L))
        if b <= L:
            return
        start = max(a, L)
        if self.fit["fill"] == "loop" and L > 2:
            # Play the last part backwards and forwards (boomerang): smooth, no jump.
            P = max(2, min(L, int(round(self.LOOP_SECONDS * self.fps))))
            tail = self._load_tail(P)
            period = 2 * (P - 1)
            for k in range(start, b):
                q = (k - L + 1) % period
                back = q if q <= P - 1 else period - q
                yield np.array(tail[P - 1 - back])
        else:
            last = self._last_frame()
            extra = max(1, self.length - L)
            for k in range(start, b):
                # Frozen frame keeps a very gentle push-in so the picture never looks dead.
                p = (k - L + 1) / extra
                z = 1.0 + 0.04 * (p * p * (3 - 2 * p))
                c = 1.0 / z  # inverse map: output pixel -> source pixel
                M = np.array([[c, 0, (self.W - 1) / 2 * (1 - c)], [0, c, (self.H - 1) / 2 * (1 - c)]])
                yield warp_exact(last, M, self.W, self.H)

    def close(self):
        self._last = None
        self._tail_mm = None
