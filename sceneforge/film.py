"""Whole-video "film finish" (paper texture, soft grain, vignette), camera shake, the paper-tear chapter
transition and the typewriter opening title.

All functions work on BGR uint8 frames of any size (sizes are scaled from a 1080p design).
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import premium as P


# ---------------------------------------------------------------------------------------------- finish
class Finish:
    """Light paper texture (+-3 %), soft film grain and a subtle vignette (corners ~16 % darker).
    Never strong enough to notice on its own - it just makes the video feel printed, not digital."""

    def __init__(self, W, H, seed=7, grain_frames=8):
        rng = np.random.default_rng(seed)
        low = cv2.resize(rng.standard_normal((27, 48)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        fib = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 0.8)
        tex = 1 + 0.018 * low / (np.abs(low).max() + 1e-6) + 0.012 * fib / (np.abs(fib).max() + 1e-6)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        vig = 1 - 0.16 * np.clip((r - 0.35) / 0.65, 0, 1) ** 1.6
        # stored as uint8 x 200, multiplied with cv2 (fast, saturating)
        m = np.clip(tex * vig * 200.0, 0, 255).astype(np.uint8)
        self.mul = cv2.merge([m, m, m])
        self.plus, self.minus = [], []
        amp = 4.0  # grain strength in 0-255 levels
        for _ in range(grain_frames):
            g = rng.standard_normal((max(1, H // 2), max(1, W // 2))).astype(np.float32)
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR) * amp
            pos = np.clip(g, 0, 255).astype(np.uint8)
            neg = np.clip(-g, 0, 255).astype(np.uint8)
            self.plus.append(cv2.merge([pos, pos, pos]))
            self.minus.append(cv2.merge([neg, neg, neg]))

    def apply(self, frame, idx):
        out = cv2.multiply(frame, self.mul, scale=1 / 200.0)
        k = idx % len(self.plus)
        cv2.add(out, self.plus[k], dst=out)
        cv2.subtract(out, self.minus[k], dst=out)
        return out


# ---------------------------------------------------------------------------------------------- camera shake
SHAKE_LEN = 0.3


def shake_offset(t, hits):
    """hits: [(time, amplitude px)]. A 0.3 s decaying shake after each hit."""
    dx = dy = 0.0
    for t0, amp in hits:
        q = t - t0
        if 0 <= q < SHAKE_LEN:
            k = amp * (1 - q / SHAKE_LEN) ** 2
            dx += k * math.sin(q * 90 + t0)
            dy += k * math.cos(q * 73 + 2 * t0)
    return dx, dy


def apply_shake(frame, dx, dy):
    if abs(dx) < 0.05 and abs(dy) < 0.05:
        return frame
    H, W = frame.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ---------------------------------------------------------------------------------------------- paper tear
TEAR_LEN = 0.75  # seconds


class Tear:
    """Freezes the outgoing frame, tears it along a jagged near-vertical line and pulls both halves away,
    revealing the next scene underneath."""

    def __init__(self, out_frame, seed):
        H, W = out_frame.shape[:2]
        u = H / 1080.0
        self.W, self.H, self.u = W, H, u
        rng = np.random.default_rng(seed)
        ys = np.arange(H, dtype=np.float32)
        base = W * rng.uniform(0.44, 0.56) + W * rng.uniform(-0.08, 0.08) * (ys / H - 0.5)
        jag = np.zeros(H, np.float32)
        for freq, amp in ((3, 22), (11, 9), (37, 5), (120, 2.5)):
            jag += amp * u * np.sin(ys / H * freq * 2 * math.pi + rng.uniform(0, 6.3))
        jag += np.repeat(rng.uniform(-3, 3, H // 4 + 1), 4)[:H] * u
        line = base + jag
        xx = np.arange(W, dtype=np.float32)[None, :]
        left = (xx < line[:, None]).astype(np.float32)
        edge_w = (6 + 4 * np.abs(np.sin(ys / (9 * u) + rng.uniform(0, 3))))[:, None] * u
        dist = xx - line[:, None]
        fibre_l = ((dist < 0) & (dist > -edge_w)).astype(np.float32)
        fibre_r = ((dist >= 0) & (dist < edge_w * 0.8)).astype(np.float32)
        of = out_frame.astype(np.float32)
        cream = np.array(P.CREAM[::-1], np.float32)
        self.pieces = []
        for mask, fib, sgn in ((left, fibre_l, -1), (1 - left, fibre_r, 1)):
            rgb = of * (1 - fib[..., None]) + cream * fib[..., None]
            a = cv2.GaussianBlur(mask, (0, 0), 0.7)
            self.pieces.append((np.dstack([rgb * a[..., None], a]).astype(np.float32), sgn))

    def draw(self, under, q):
        """under: BGR uint8 frame of the incoming scene; q: 0..1 progress. Returns BGR uint8."""
        W, H, u = self.W, self.H, self.u
        e = q ** 2.2
        out = under.astype(np.float32)
        for rgba, sgn in self.pieces:
            M = cv2.getRotationMatrix2D((W / 2 + sgn * W * 0.25, H), sgn * 7 * e, 1.0)
            M[0, 2] += sgn * W * 0.62 * e
            M[1, 2] += -H * 0.05 * e + 9 * u * math.sin(math.pi * q)
            p = cv2.warpAffine(rgba, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            sh = cv2.GaussianBlur(p[..., 3], (0, 0), max(1.0, 14 * u)) * 0.45
            sh = np.roll(sh, (int(10 * u), int(8 * u) * sgn), (0, 1))
            out *= (1 - sh[..., None])
            out *= (1 - p[..., 3:4])
            out += p[..., :3]
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------- opening
def aged_paper(W, H, seed=3):
    """Warm cream paper with tea stains and burnt edges (BGR float32)."""
    rng = np.random.default_rng(seed)
    u = H / 1080.0
    base = np.zeros((H, W, 3), np.float32) + np.array([186, 216, 231], np.float32)  # BGR of (231, 216, 186)
    low = cv2.resize(rng.standard_normal((9, 16)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    base *= (1 + 0.05 * low / np.abs(low).max())[..., None]
    for _ in range(7):
        m = np.zeros((H, W), np.float32)
        cx, cy, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(80, 260) * u
        cv2.circle(m, (int(cx), int(cy)), max(2, int(r)), 1.0, -1)
        ring = m - cv2.erode(m, np.ones((9, 9), np.uint8))
        m = cv2.GaussianBlur(m, (0, 0), max(1, r * 0.35)) * 0.05 + cv2.GaussianBlur(ring, (0, 0), max(1, 4 * u)) * 0.06
        base *= (1 - m[..., None] * np.array([1.0, 0.6, 0.3], np.float32))
    fib = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 0.9)
    base += fib[..., None] * 6
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx, W - xx) / W, np.minimum(yy, H - yy) / H)
    burn = np.clip(1 - edge / 0.09, 0, 1) ** 2
    base *= (1 - 0.32 * burn[..., None] * np.array([1.25, 1.0, 0.8], np.float32))
    return np.clip(base, 0, 255)


class Opening:
    """The standard opening: on aged paper, the title is typed letter by letter (clack per letter, blinking
    caret), a bell rings, a red stamp thumps in under it, then the page tears away into scene 1.

    Times (seconds from the start of the video) are in .events for the sound track."""

    FADE_IN = 0.4
    TYPE_START = 0.55

    def __init__(self, title, stamp_text, W, H, seed=11):
        self.W, self.H = W, H
        u = self.u = H / 1080.0
        self.paper = aged_paper(W, H)
        title = " ".join((title or "").upper().split())
        f = P.font("elite", 112 * u)
        words = title.split()
        lines = [title]
        maxw = W * 0.80
        if f.getlength(title) > maxw and len(words) > 1:
            best = None
            for k in range(1, len(words)):
                l1, l2 = " ".join(words[:k]), " ".join(words[k:])
                wmax = max(f.getlength(l1), f.getlength(l2))
                if best is None or wmax < best[0]:
                    best = (wmax, [l1, l2])
            lines = best[1]
            if "OF" in words[1:]:  # "THE ENTIRE HISTORY / OF NVIDIA" reads better than a pure width balance
                k = len(words) - 1 - words[::-1].index("OF")
                l1, l2 = " ".join(words[:k]), " ".join(words[k:])
                if max(f.getlength(l1), f.getlength(l2)) <= maxw:
                    lines = [l1, l2]
            while max(f.getlength(x) for x in lines) > maxw and f.size > 30:
                f = P.font("elite", f.size * 0.92)
        self.f, self.lines = f, lines
        self.lh = f.size * 1.21
        top = H / 2 - 70 * u - self.lh * len(lines) / 2
        self.pos = [(W / 2 - f.getlength(x) / 2, top + i * self.lh) for i, x in enumerate(lines)]
        self.total = sum(len(x) for x in lines)
        self.char_dt = min(0.085, 2.9 / max(1, self.total))
        self.type_end = self.TYPE_START + self.char_dt * self.total
        self.bell_t = self.type_end + 0.12
        rng = np.random.default_rng(seed)
        self.stamp = P.Stamp(stamp_text, 64 * u, rng, u) if stamp_text else None
        self.stamp_angle = float(rng.uniform(4, 8) * (1 if rng.random() < 0.5 else -1))
        self.stamp_t = self.bell_t + 0.45 if self.stamp else None
        self.stamp_pos = (W / 2, top + self.lh * len(lines) + 120 * u)
        self.tear_t = max(4.6, (self.stamp_t or self.bell_t) + 1.0)
        self.duration = self.tear_t + TEAR_LEN
        self._cache = (None, None)
        self.events = [(self.TYPE_START + self.char_dt * i, "clack") for i in range(self.total)
                       if self._char(i) != " "]
        self.events.append((self.bell_t, "bell"))
        if self.stamp:
            self.events.append((self.stamp_t, "stamp"))
        self.events += [(self.tear_t, "tear"), (self.tear_t - 0.1, "whoosh")]

    def _char(self, i):
        for x in self.lines:
            if i < len(x):
                return x[i]
            i -= len(x)
        return " "

    def page(self, t):
        """The paper page at time t (before the tear), BGR uint8."""
        n = int(min(max((t - self.TYPE_START) / self.char_dt + 1e-6, 0), self.total)) if t >= self.TYPE_START else 0
        caret = (t < self.type_end + 0.6) and (int(t * 3) % 2 == 0 or t < self.type_end)
        key = (n, caret)
        if self._cache[0] != key:
            rgb = self.paper[..., ::-1].astype(np.uint8)
            img = Image.fromarray(np.ascontiguousarray(rgb), "RGB").convert("RGBA")
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            left, last = n, None
            for (x, y), line in zip(self.pos, self.lines):
                k = min(left, len(line))
                if k > 0 or last is None:
                    d.text((x, y), line[:k], font=self.f, fill=P.INK + (235,))
                    last = (x + self.f.getlength(line[:k]), y)
                left -= len(line)
                if left <= 0:
                    break
            if caret and last:
                u = self.u
                d.rectangle([last[0] + 6 * u, last[1] + 14 * u, last[0] + 12 * u, last[1] + self.f.size * 0.93],
                            fill=P.INK + (220,))
            img.alpha_composite(lay)
            self._cache = (key, np.ascontiguousarray(np.asarray(img.convert("RGB"))[..., ::-1]))
        fr = self._cache[1].copy()
        if self.stamp and t >= self.stamp_t:
            from .effects import blit
            lt = t - self.stamp_t
            blit(fr, self.stamp.spr, self.stamp.anchor, self.stamp_pos[0], self.stamp_pos[1],
                 scale=P.stamp_scale(lt), opacity=min(1.0, lt / 0.08), angle=self.stamp_angle)
        if t < self.FADE_IN:
            fr = (fr.astype(np.float32) * (t / self.FADE_IN)).astype(np.uint8)
        if self.stamp and self.stamp_t <= t < self.stamp_t + SHAKE_LEN:
            fr = apply_shake(fr, *shake_offset(t, [(self.stamp_t, 10 * self.u)]))
        return fr
