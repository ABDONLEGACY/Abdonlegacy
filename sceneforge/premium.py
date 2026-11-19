"""Premium effect sprites: torn paper tags, rubber stamps, typewriter lower-thirds, sticky notes, quote cards and
hand-drawn marker circles.

Everything is drawn with Pillow at 2x and shrunk (smooth edges), at a size given in pixels for the frame being
rendered, and returned as premultiplied BGRA float32 (0..1) - the format effects.blit() composites.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import paths

CREAM = (242, 235, 221)
INK = (43, 37, 34)
BRASS = (217, 139, 43)
RED = (184, 50, 42)
STAMP_RED = (186, 36, 32)
STICKY = (244, 214, 110)
SS = 2

FONT_FILES = {"caveat": "Caveat-Variable.ttf", "elite": "SpecialElite-Regular.ttf",
              "alfa": "AlfaSlabOne-Regular.ttf", "lora_italic": "Lora-Italic-Variable.ttf"}
_FONTS = {}


def font(kind, size):
    """One of the bundled premium fonts (Caveat Bold, Special Elite, Alfa Slab One, Lora Italic)."""
    size = max(6, int(round(size)))
    key = (kind, size)
    if key not in _FONTS:
        if len(_FONTS) > 80:
            _FONTS.clear()
        try:
            f = ImageFont.truetype(str(paths.FONTS_DIR / FONT_FILES[kind]), size)
            try:
                if kind == "caveat":
                    f.set_variation_by_axes([700])
                elif kind == "lora_italic":
                    f.set_variation_by_axes([500])
            except Exception:
                pass
        except Exception:
            from . import fonts
            f = fonts.load("Arial Bold", size)
        _FONTS[key] = f
    return _FONTS[key]


def to_premult(img):
    """PIL RGBA -> premultiplied BGRA float32 (0..1)."""
    a = np.asarray(img).astype(np.float32) / 255.0
    out = np.empty_like(a)
    out[..., :3] = a[..., 2::-1] * a[..., 3:4]
    out[..., 3] = a[..., 3]
    return out


def _down(img):
    return img.resize((max(1, img.width // SS), max(1, img.height // SS)), Image.LANCZOS)


def ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def pop_scale(t):
    """0.6 -> 1.08 -> 1.0 in 0.25 s (paper tags, sticky notes)."""
    if t < 0:
        return 0.6
    if t < 0.15:
        return 0.6 + 0.48 * ease_out(t / 0.15)
    if t < 0.25:
        return 1.08 - 0.08 * smooth((t - 0.15) / 0.10)
    return 1.0


def stamp_scale(t):
    """Rubber-stamp thump: 1.9 -> 0.94 in 0.11 s, settles to 1.0 by 0.2 s."""
    if t < 0:
        return 1.9
    if t < 0.11:
        u = t / 0.11
        return 1.9 - 0.96 * u * u
    if t < 0.2:
        return 0.94 + 0.06 * smooth((t - 0.11) / 0.09)
    return 1.0


def extent(spr, anchor):
    """Tight box (left, top, right, bottom) of the visible pixels, relative to the anchor."""
    ys, xs = np.nonzero(spr[..., 3] > 0.04)
    if not len(xs):
        return (0.0, 0.0, 0.0, 0.0)
    return (float(xs.min() - anchor[0]), float(ys.min() - anchor[1]), float(xs.max() + 1 - anchor[0]),
            float(ys.max() + 1 - anchor[1]))


# ---------------------------------------------------------------------------------------------- paper
def _torn_poly(x0, y0, x1, y1, rng, step, amp):
    pts = []

    def edge(ax, ay, bx, by):
        n = max(2, int(math.hypot(bx - ax, by - ay) / step))
        for i in range(n):
            u = i / n
            px, py = ax + (bx - ax) * u, ay + (by - ay) * u
            nx, ny = -(by - ay), (bx - ax)
            L = math.hypot(nx, ny) or 1
            j = rng.uniform(-amp, amp)
            pts.append((px + nx / L * j, py + ny / L * j))
    edge(x0, y0, x1, y0)
    edge(x1, y0, x1, y1)
    edge(x1, y1, x0, y1)
    edge(x0, y1, x0, y0)
    return pts


def paper(size, rect, rng, u, opacity=0.94, color=CREAM, amp=3.5, shadow=True):
    """Torn paper (drawn at 2x) with a soft shadow, on a transparent canvas. u = pixel scale of the frame."""
    Wc, Hc = size
    img = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
    x0, y0, x1, y1 = rect
    poly = _torn_poly(x0, y0, x1, y1, rng, step=max(4, 14 * SS * u), amp=amp * SS * u)
    if shadow:
        sh = Image.new("L", (Wc, Hc), 0)
        ImageDraw.Draw(sh).polygon([(px + 5 * SS * u, py + 8 * SS * u) for px, py in poly], fill=110)
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, 9 * SS * u)))
        img.paste(Image.new("RGBA", (Wc, Hc), (20, 14, 10, 255)), (0, 0), sh)
    mask = Image.new("L", (Wc, Hc), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=int(255 * opacity))
    grain = (rng.standard_normal((Hc, Wc)) * 5).astype(np.int16)
    base = np.clip(np.zeros((Hc, Wc, 3), np.int16) + np.array(color, np.int16) + grain[..., None], 0, 255)
    img.paste(Image.fromarray(base.astype(np.uint8), "RGB").convert("RGBA"), (0, 0), mask)
    return img


def _wobble_line(draw, x0, x1, y, width, rng, color=RED):
    n = max(8, int((x1 - x0) / 3))
    ph = rng.uniform(0, 6.28)
    slope = rng.uniform(-3, 3) * width / 8
    pts = []
    for i in range(n + 1):
        q = i / n
        pts.append((x0 + (x1 - x0) * q,
                    y + width * 0.28 * math.sin(ph + q * 5.5) + slope * (q - 0.5) + width * 0.12 * math.sin(ph * 3 + q * 17)))
    r = width / 2
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        steps = max(1, int(math.hypot(bx - ax, by - ay) / 2))
        g = i / len(pts)
        rr = r * (0.75 + 0.25 * math.sin(math.pi * min(1, g * 1.05)))
        for k in range(steps):
            q = k / steps
            cx, cy = ax + (bx - ax) * q, ay + (by - ay) * q
            draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (255,))


# ---------------------------------------------------------------------------------------------- [TEXT] paper tag
class PaperTag:
    """Hand-written text (Caveat Bold) on a torn cream paper tag, with a red underline revealed separately."""

    def __init__(self, text, size, max_w, rng, u):
        while True:
            f = font("caveat", size * SS)
            bb = f.getbbox(text)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            if tw / SS <= max_w - 70 * u or size < 20:
                break
            size *= 0.92
        padx, pady, uline, m = 34 * SS * u, 14 * SS * u, 26 * SS * u, 30 * SS * u
        Wc, Hc = int(tw + 2 * padx + 2 * m), int(th + 2 * pady + uline + 2 * m)
        img = paper((Wc, Hc), (m, m, Wc - m, Hc - m), rng, u, opacity=0.93)
        ImageDraw.Draw(img).text((m + padx - bb[0], m + pady - bb[1]), text, font=f, fill=INK + (255,))
        ul = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        _wobble_line(ImageDraw.Draw(ul), m + padx - 8 * SS * u, m + padx + tw + 8 * SS * u, m + pady + th + 14 * SS * u,
                     8 * SS * u, rng)
        self.base = to_premult(_down(img))
        self.line = to_premult(_down(ul))
        self.line_x = ((m + padx - 10 * SS * u) / SS, (m + padx + tw + 10 * SS * u) / SS)
        self.anchor = (self.base.shape[1] / 2, self.base.shape[0] / 2)
        self.extent = extent(self.base, self.anchor)


# ---------------------------------------------------------------------------------------------- [STAMP]
class Stamp:
    """Red rubber stamp (Alfa Slab One, double border, worn speckled ink). card=True puts it on a cream card."""

    def __init__(self, text, size, rng, u, card=False):
        text = " ".join(text.upper().split())
        f = font("alfa", size * SS)
        bb = f.getbbox(text)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        S = SS * u
        pad_x, pad_y, m = 40 * S, 26 * S, 30 * S
        bw, bh = tw + 2 * pad_x, th + 2 * pad_y
        Wc, Hc = int(bw + 2 * m), int(bh + 2 * m)
        ink = Image.new("L", (Wc, Hc), 0)
        d = ImageDraw.Draw(ink)
        d.rounded_rectangle([m, m, m + bw, m + bh], max(1, int(16 * S)), outline=255, width=max(1, int(9 * S)))
        d.rounded_rectangle([m + 16 * S, m + 16 * S, m + bw - 16 * S, m + bh - 16 * S], max(1, int(9 * S)), outline=255,
                            width=max(1, int(3 * S)))
        d.text((m + pad_x - bb[0], m + pad_y - bb[1]), text, font=f, fill=255)
        a = np.asarray(ink).astype(np.float32) / 255.0
        cell = max(4, int(40 * S))
        low = cv2.resize(rng.uniform(0.55, 1.0, (Hc // cell + 2, Wc // cell + 2)).astype(np.float32), (Wc, Hc),
                         interpolation=cv2.INTER_CUBIC)
        speck = (rng.random((Hc // 3 + 1, Wc // 3 + 1)) > 0.10).astype(np.float32)
        speck = cv2.GaussianBlur(cv2.resize(speck, (Wc, Hc), interpolation=cv2.INTER_NEAREST), (0, 0), max(0.5, 1.2 * S))
        low = 0.75 + 0.25 * (low - 0.55) / 0.45
        a = np.clip(a * np.clip(low, 0, 1) * np.clip(speck * 1.15, 0, 1) * 0.95, 0, 1)
        img = np.zeros((Hc, Wc, 4), np.uint8)
        img[..., :3] = STAMP_RED
        img[..., 3] = (a * 255).astype(np.uint8)
        stamp = Image.fromarray(img, "RGBA")
        if card:
            cm = int(26 * S)
            base = paper((Wc + 2 * cm, Hc + 2 * cm), (cm + m - 22 * S, cm + m - 22 * S, cm + m + bw + 22 * S,
                                                      cm + m + bh + 22 * S), rng, u, opacity=0.96, amp=3)
            base.alpha_composite(stamp, (cm, cm))
            stamp = base
        self.spr = to_premult(_down(stamp))
        self.anchor = (self.spr.shape[1] / 2, self.spr.shape[0] / 2)
        self.extent = extent(self.spr, self.anchor)


# ---------------------------------------------------------------------------------------------- [TYPE] lower-third
class LowerThird:
    """Typewriter text (Special Elite) on a cream paper strip with a red edge; typed letter by letter."""

    def __init__(self, text, size, rng, u):
        self.text = text
        self.f = font("elite", size)
        bb = self.f.getbbox(text or "M")
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        m, px, py = 30 * u, 34 * u, 20 * u
        self.w, self.h = int(tw + 2 * px + 2 * m + 10 * u), int(th + 2 * py + 2 * m)
        bg = paper((self.w * SS, self.h * SS), (m * SS, m * SS, (self.w - m) * SS, (self.h - m) * SS), rng, u,
                   opacity=0.95, amp=2.5)
        ImageDraw.Draw(bg).rectangle([m * SS, m * SS, (m + 8 * u) * SS, (self.h - m) * SS], fill=RED + (255,))
        self.bg = _down(bg)
        self.tx, self.ty = m + px - bb[0] + 4 * u, m + py - bb[1]
        self.u = u
        self.margin = m
        self.anchor = (m, self.h / 2)  # left edge of the strip
        self._cache = (None, None)

    def sprite(self, n, caret):
        key = (n, caret)
        if self._cache[0] != key:
            img = self.bg.copy()
            d = ImageDraw.Draw(img)
            d.text((self.tx, self.ty), self.text[:n], font=self.f, fill=INK + (255,))
            if caret:
                x = self.tx + self.f.getlength(self.text[:n]) + 4 * self.u
                d.rectangle([x, self.ty + 4 * self.u, x + 4 * self.u, self.ty + self.f.size * 0.85], fill=INK + (255,))
            self._cache = (key, to_premult(img))
        return self._cache[1]


# ---------------------------------------------------------------------------------------------- [NOTE] sticky note
def wrap(text, max_chars=16, max_lines=3):
    if " / " in text:
        return [x.strip() for x in text.split(" / ") if x.strip()][:max_lines + 1]
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


class Sticky:
    """Yellow sticky note with a strip of tape, hand-written (Caveat Bold)."""

    def __init__(self, text, size, rng, u):
        S = SS * u
        lines = wrap(text)
        f = font("caveat", size * SS)
        lh = int(size * 1.05 * SS)
        tw = max(f.getlength(x) for x in lines)
        side = int(max(tw + 70 * S, 300 * S, len(lines) * lh + 110 * S))
        m = int(34 * S)
        Wc = Hc = side + 2 * m
        img = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        sh = Image.new("L", (Wc, Hc), 0)
        ImageDraw.Draw(sh).polygon([(m + 8 * S, m + 14 * S), (m + side + 6 * S, m + 10 * S),
                                    (m + side + 10 * S, m + side + 16 * S), (m + 12 * S, m + side + 8 * S)], fill=120)
        img.paste(Image.new("RGBA", (Wc, Hc), (25, 18, 10, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(max(1, 10 * S))))
        note = np.zeros((side, side, 3), np.float32) + np.array(STICKY, np.float32)
        yy = np.linspace(0, 1, side)[:, None]
        note *= (1 - 0.07 * yy ** 2)[..., None]
        note += rng.standard_normal((side, side, 1)) * 3
        img.paste(Image.fromarray(np.clip(note, 0, 255).astype(np.uint8), "RGB").convert("RGBA"), (m, m))
        d = ImageDraw.Draw(img)
        y = m + (side - len(lines) * lh) / 2 + 10 * S
        for x in lines:
            d.text((m + (side - f.getlength(x)) / 2, y), x, font=f, fill=INK + (255,))
            y += lh
        tape = Image.new("RGBA", (int(side * 0.42), max(2, int(34 * S))), (236, 228, 205, 170))
        tape = tape.rotate(rng.uniform(-6, 6), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(tape, (int(m + side / 2 - tape.width / 2), max(0, int(m - tape.height / 2))))
        self.spr = to_premult(_down(img))
        self.anchor = (self.spr.shape[1] / 2, self.spr.shape[0] / 2)
        self.extent = extent(self.spr, self.anchor)


# ---------------------------------------------------------------------------------------------- [QUOTE] card
class QuoteCard:
    """Cream paper card with a big brass quotation mark; the quote (Lora Italic) is typed letter by letter, then
    the attribution (Caveat, brass) fades in."""

    def __init__(self, quote, attribution, rng, u, max_w):
        self.quote = quote.replace("'", "’").strip().strip('"“”')
        self.attr = ("— " + attribution.strip()) if attribution and attribution.strip() else ""
        f = font("lora_italic", 54 * u)
        inner = max_w - 220 * u
        lines, cur = [], ""
        for w in self.quote.split():
            test = (cur + " " + w).strip()
            if f.getlength(test) > inner and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        lines.append(cur)
        self.lines, self.f = lines, f
        self.fa = font("caveat", 46 * u)
        lh = 74 * u
        text_w = max([f.getlength(x) for x in lines] + [self.fa.getlength(self.attr) if self.attr else 0])
        cw = min(max_w, text_w + 220 * u)
        ch = 70 * u + lh * len(lines) + (30 + 56) * u * (1 if self.attr else 0.4) + 50 * u
        m = 30 * u
        self.w, self.h = int(cw + 2 * m), int(ch + 2 * m)
        bg = paper((self.w * SS, self.h * SS), (m * SS, m * SS, (self.w - m) * SS, (self.h - m) * SS), rng, u,
                   opacity=0.97, amp=3)
        ImageDraw.Draw(bg).text(((m + 26 * u) * SS, (m - 18 * u) * SS), "“", font=font("lora_italic", 170 * u * SS),
                                fill=BRASS + (255,))
        self.bg = _down(bg)
        self.tx, self.ty, self.lh = m + 110 * u, m + 70 * u, lh
        self.total = sum(len(x) for x in lines) + len(lines) - 1
        self.anchor = (self.w / 2, self.h / 2)
        self._cache = (None, None)

    def sprite(self, nchars, attr_alpha):
        key = (nchars, round(attr_alpha, 2))
        if self._cache[0] != key:
            img = self.bg.copy()
            d = ImageDraw.Draw(img)
            left, y = nchars, self.ty
            for x in self.lines:
                if left <= 0:
                    break
                d.text((self.tx, y), x[:left], font=self.f, fill=INK + (255,))
                left -= len(x) + 1
                y += self.lh
            if attr_alpha > 0 and self.attr:
                lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(lay).text((self.tx, self.ty + self.lh * len(self.lines) + 22 * (self.lh / 74)), self.attr,
                                         font=self.fa, fill=BRASS + (int(255 * attr_alpha),))
                img = Image.alpha_composite(img, lay)
            self._cache = (key, to_premult(img))
        return self._cache[1]


# ---------------------------------------------------------------------------------------------- [CIRCLE]
def marker_loop(rx, ry, rng, n=120):
    """Hand-drawn marker loop around (0, 0): starts near 10 o'clock, goes round once and overshoots a little."""
    a0 = math.radians(rng.uniform(190, 215))
    span = math.radians(rng.uniform(395, 415))
    t = np.linspace(0, 1, n)
    ang = a0 + span * t
    wob = 1 + 0.035 * np.sin(t * 9 + rng.uniform(0, 6)) + 0.06 * t
    tilt = math.radians(rng.uniform(-6, 6))
    x, y = rx * wob * np.cos(ang), ry * wob * np.sin(ang)
    return np.stack([x * math.cos(tilt) - y * math.sin(tilt), x * math.sin(tilt) + y * math.cos(tilt)], 1)


def draw_stroke(frame, pts, color_rgb, width, opacity=1.0):
    """Anti-aliased polyline with a thin cream edge, composited onto a BGR uint8 frame."""
    if len(pts) < 2 or opacity <= 0:
        return
    Hf, Wf = frame.shape[:2]
    pad = width * 2 + 4
    x0, y0 = int(max(0, math.floor(pts[:, 0].min() - pad))), int(max(0, math.floor(pts[:, 1].min() - pad)))
    x1, y1 = int(min(Wf, math.ceil(pts[:, 0].max() + pad))), int(min(Hf, math.ceil(pts[:, 1].max() + pad)))
    if x1 <= x0 or y1 <= y0:
        return
    layer = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    pp = ((pts - [x0, y0]) * 16).astype(np.int32)
    cv2.polylines(layer, [pp], False, CREAM[::-1] + (150,), max(1, int(round(width * 1.6))), cv2.LINE_AA, 4)
    cv2.polylines(layer, [pp], False, color_rgb[::-1] + (255,), max(1, int(round(width))), cv2.LINE_AA, 4)
    a = layer[..., 3:4].astype(np.float32) / 255.0 * opacity
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = np.clip(roi * (1 - a) + layer[..., :3].astype(np.float32) * a + 0.5, 0, 255).astype(np.uint8)
