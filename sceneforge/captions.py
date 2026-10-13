"""Burned-in animated captions, timed to the spoken words but spelled like the script.

Modes:
  word    - a short phrase is shown and the word being spoken is highlighted (karaoke style)
  phrase  - short phrases (2-5 words) appear in time with the voice
  single  - one word at a time
"""
import bisect
import hashlib
import json
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fonts

END_PUNCT = re.compile(r"[.!?;:]['\"”’)]*$")
COMMA = re.compile(r"[,—–]['\"”’)]*$")
LINGER = 0.4  # seconds a caption stays after its last word if nothing follows


def hex_to_rgb(h, default=(255, 255, 255)):
    try:
        h = h.strip().lstrip("#")
        if h.startswith("rgba(") or h.startswith("rgb("):
            nums = [float(x) for x in re.findall(r"[\d.]+", h)[:3]]
            return tuple(int(round(v)) for v in nums)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def make_groups(words, cfg):
    """Split the word list into caption groups (never across scenes or long pauses)."""
    mode = cfg.get("mode", "word")
    max_words = 1 if mode == "single" else max(2, min(8, int(cfg.get("max_words", 4))))
    groups, cur = [], []

    def flush():
        if cur:
            groups.append(list(cur))
            cur.clear()

    for i, w in enumerate(words):
        if cur:
            prev = cur[-1]
            if (w["scene"] != prev["scene"] or w["s"] - prev["e"] > 0.7 or len(cur) >= max_words):
                flush()
        cur.append(w)
        if mode != "single" and (END_PUNCT.search(w["text"]) or (COMMA.search(w["text"]) and len(cur) >= 2)):
            flush()
    flush()
    # Avoid lonely one-word captions in phrase/word modes: merge into the previous group when possible.
    if mode != "single":
        merged = []
        for g in groups:
            if (len(g) == 1 and merged and merged[-1][-1]["scene"] == g[0]["scene"]
                    and len(merged[-1]) < max_words + 1 and g[0]["s"] - merged[-1][-1]["e"] < 0.5
                    and not END_PUNCT.search(merged[-1][-1]["text"])):
                merged[-1].extend(g)
            else:
                merged.append(g)
        groups = merged
    out = []
    for gi, g in enumerate(groups):
        start = g[0]["s"]
        end = g[-1]["e"] + LINGER
        if gi + 1 < len(groups):
            end = min(end, groups[gi + 1][0]["s"])
        end = max(end, g[-1]["e"])
        out.append({"words": [{"text": w["text"], "s": w["s"], "e": w["e"]} for w in g], "s": start, "e": end})
    return out


class CaptionRenderer:
    def __init__(self, words, cfg, W, H, fps):
        self.cfg = cfg
        self.W, self.H, self.fps = W, H, fps
        self.enabled = bool(cfg.get("enabled")) and bool(words)
        self.groups = make_groups(words, cfg) if self.enabled else []
        self.starts = [int(round(g["s"] * fps)) for g in self.groups]
        self.ends = [max(self.starts[i] + 1, int(round(g["e"] * fps))) for i, g in enumerate(self.groups)]
        scale = min(W, H) / 1080.0
        self.size = max(10, int(round(float(cfg.get("size", 64)) * scale)))
        self.outline = max(0, int(round(float(cfg.get("outline", 4)) * scale)))
        self.font = fonts.load(cfg.get("font"), self.size)
        self.font_pop = fonts.load(cfg.get("font"), int(round(self.size * 1.12)))
        self.color = hex_to_rgb(cfg.get("color", "#FFFFFF"))
        self.hl = hex_to_rgb(cfg.get("highlight_color", "#FFD400"), (255, 212, 0))
        self.oc = hex_to_rgb(cfg.get("outline_color", "#000000"), (0, 0, 0))
        portrait = H > W
        self.max_w = int(W * (0.86 if portrait else 0.82))
        self._cache = {}

    def signature(self, f0, f1):
        """Hash of everything that affects captions in global frames [f0, f1) (for resume / re-render)."""
        if not self.enabled:
            return "off"
        lo = bisect.bisect_right(self.starts, f1)
        items = [(self.starts[i], self.ends[i], self.groups[i]["words"])
                 for i in range(max(0, bisect.bisect_right(self.starts, f0) - 2), lo)
                 if self.ends[i] > f0 and self.starts[i] < f1]
        blob = json.dumps([items, self.cfg, self.W, self.H], sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()[:16]

    # ---- drawing ---------------------------------------------------------------
    def _text(self, t):
        return t.upper() if self.cfg.get("uppercase") else t

    def _layout(self, gi):
        g = self.groups[gi]
        draw = ImageDraw.Draw(Image.new("L", (8, 8)))
        space = draw.textlength(" ", font=self.font)
        widths = [draw.textlength(self._text(w["text"]), font=self.font) for w in g["words"]]
        if self.cfg.get("pop", True) and self.cfg.get("mode", "word") == "word":
            # leave room so the slightly enlarged active word never touches its neighbours
            space += max(draw.textlength(self._text(w["text"]), font=self.font_pop) - wd
                         for w, wd in zip(g["words"], widths))
        lines, cur, cur_w = [], [], 0.0
        for i, wd in enumerate(widths):
            add = wd if not cur else cur_w + space + wd
            if cur and add > self.max_w:
                lines.append((cur, cur_w))
                cur, cur_w = [i], wd
            else:
                cur.append(i)
                cur_w = add
        if cur:
            lines.append((cur, cur_w))
        asc, desc = self.font.getmetrics()
        line_h = int((asc + desc) * 1.12)
        pad = self.outline + int(self.size * 0.25)
        block_w = int(max(w for _, w in lines)) + 2 * pad
        block_h = line_h * len(lines) + 2 * pad
        pos = {}
        for li, (idxs, lw) in enumerate(lines):
            x = pad + (block_w - 2 * pad - lw) / 2
            y = pad + li * line_h
            for i in idxs:
                pos[i] = (x, y, widths[i])
                x += widths[i] + space
        return block_w, block_h, pos, line_h

    def _render_state(self, gi, active):
        key = (gi, active)
        if key in self._cache:
            return self._cache[key]
        if len(self._cache) > 400:
            self._cache.clear()
        g = self.groups[gi]
        bw, bh, pos, line_h = self._layout(gi)
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        mode = self.cfg.get("mode", "word")
        pop = bool(self.cfg.get("pop", True)) and mode == "word"
        layers = []
        for i, w in enumerate(g["words"]):
            x, y, wd = pos[i]
            is_active = (i == active) and mode == "word"
            font = self.font_pop if (is_active and pop) else self.font
            color = self.hl if is_active else self.color
            if is_active and pop:
                # draw slightly bigger, centred on the word's normal slot
                big_w = ImageDraw.Draw(img).textlength(self._text(w["text"]), font=font)
                x -= (big_w - wd) / 2
                y -= (self.size * 0.12) / 2
            layers.append((x, y, self._text(w["text"]), font, color))
        if self.cfg.get("shadow", True):
            sh = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            off = max(1, int(self.size * 0.05))
            for x, y, t, font, _ in layers:
                sd.text((x + off, y + off), t, font=font, fill=(0, 0, 0, 150),
                        stroke_width=self.outline, stroke_fill=(0, 0, 0, 150))
            sh = sh.filter(ImageFilter.GaussianBlur(max(1, self.size * 0.05)))
            img = Image.alpha_composite(img, sh)
        d = ImageDraw.Draw(img)
        for x, y, t, font, color in layers:
            d.text((x, y), t, font=font, fill=color + (255,), stroke_width=self.outline,
                   stroke_fill=self.oc + (255,))
        arr = np.asarray(img)
        bgr = np.ascontiguousarray(arr[:, :, 2::-1])
        alpha = arr[:, :, 3:4].astype(np.uint16)
        self._cache[key] = (bgr, alpha)
        return bgr, alpha

    def _place(self, bw, bh):
        x = (self.W - bw) // 2
        pos = self.cfg.get("position", "bottom")
        if pos == "middle":
            y = (self.H - bh) // 2
        elif pos == "top":
            y = int(self.H * 0.08)
        else:
            margin = 0.22 if self.H > self.W else 0.08
            y = int(self.H * (1 - margin)) - bh
        return x, y

    def draw(self, frame, fidx):
        """Draw the caption for global frame index `fidx` onto `frame` (BGR, modified in place)."""
        if not self.enabled:
            return frame
        gi = bisect.bisect_right(self.starts, fidx) - 1
        if gi < 0 or fidx >= self.ends[gi]:
            return frame
        g = self.groups[gi]
        t = fidx / self.fps
        active = -1
        for i, w in enumerate(g["words"]):
            if t >= w["s"] - 0.5 / self.fps:
                active = i
        active = max(active, 0)
        if self.cfg.get("mode") != "word":
            active = -1
        bgr, alpha = self._render_state(gi, active)
        # entrance animation: quick pop / fade over the first few frames of each caption
        age = fidx - self.starts[gi]
        if self.cfg.get("pop", True) and age < 4:
            s = 0.88 + 0.12 * (age + 1) / 4
            a_mul = (age + 1) / 4
            h0, w0 = bgr.shape[:2]
            nw, nh = max(1, int(w0 * s)), max(1, int(h0 * s))
            bgr = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
            alpha = (cv2.resize(alpha[:, :, 0].astype(np.uint8), (nw, nh), interpolation=cv2.INTER_AREA)
                     .astype(np.float32) * a_mul).astype(np.uint16)[:, :, None]
            x, y = self._place(w0, h0)
            x += (w0 - nw) // 2
            y += (h0 - nh) // 2
        else:
            x, y = self._place(bgr.shape[1], bgr.shape[0])
        _composite(frame, bgr, alpha, x, y)
        return frame


def _composite(frame, bgr, alpha, x, y):
    H, W = frame.shape[:2]
    h, w = bgr.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    src = bgr[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.uint16)
    a = alpha[y0 - y:y1 - y, x0 - x:x1 - x]
    dst = frame[y0:y1, x0:x1].astype(np.uint16)
    frame[y0:y1, x0:x1] = ((src * a + dst * (255 - a) + 127) // 255).astype(np.uint8)
