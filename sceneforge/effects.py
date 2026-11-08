"""Scene effects: animated map pins and pop-up text drawn on top of a scene, timed to a spoken word.

Positions are stored as fractions of the scene's picture (0..1), so they work at any resolution and stay
locked to the same spot on the picture while the camera zooms and pans.

Timing (T = measured start of the trigger word):
  pin   falls during the 0.32 s before T and lands exactly at T (small bounce, shadow, ripple ring),
        an optional label slides in just after landing
  text  pops in at T (quick scale-in with a slight overshoot)
Both stay until the scene ends and leave with the scene's transition. Sounds play at T.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fonts
from .captions import hex_to_rgb

FALL = 0.32      # seconds the pin falls before it lands on the word
BOUNCE = 0.22
RIPPLE = 0.7
LABEL_DELAY = 0.12
TEXT_POP = 0.28
HAND_IN = 0.30   # hand-lettered text: calm fade + scale-in from 90 %
LINE_DELAY = 0.30  # the underline starts drawing right after the text has appeared ...
LINE_DRAW = 0.50   # ... and takes this long, left to right
TILT_RANGE = (-4.0, 2.0)  # degrees; one fixed random tilt per text (same on every render)
SAFE = 0.04      # text stays this far (fraction of the frame) inside the frame edges
SS = 4           # supersampling when drawing sprites, for smooth edges
TEXT_STYLES = {"hand_underline": "Hand-lettered + underline", "classic": "Classic pop"}

DEFAULT_STYLE = {
    "text_style": "hand_underline",
    "hand_font": "Itim", "hand_size": 150, "hand_color": "#262523", "hand_halo": "#F5F2EA",
    "underline": True, "underline_color": "#C34D48",
    "pin_color": "#E53935", "pin_size": 90,
    "text_font": "Arial Bold", "text_size": 96, "text_color": "#FFFFFF",
    "text_outline_color": "#000000", "text_outline": 6, "text_box": False, "box_color": "#000000",
    "label_size": 44,
}


# ---------------------------------------------------------------------------------------------- timing
def tilt_for(seed, scene_number, i):
    import random
    return round(random.Random(f"{seed}:{scene_number}:{i}:tilt").uniform(*TILT_RANGE), 3)


def resolve(project, words=None, auto=True):
    """{scene number: [effect, ...]} with each effect's position, tilt and trigger time "t" (seconds, measured
    from the audio; None until the scenes are synced). Text you haven't placed yourself is put automatically
    in the emptiest part of the picture."""
    words = project.words() if words is None else words
    by_scene = {}
    for w in words:
        by_scene.setdefault(w["scene"], []).append(w)
    style = {**DEFAULT_STYLE, **(project.settings.get("effects") or {})}
    placer = AutoPlacer(project, style) if auto else None
    out = {}
    for si, sc in enumerate(project.scenes):
        effects = sc.get("effects") or []
        if not effects:
            continue
        sw = by_scene.get(si, [])
        items = []
        for i, e in enumerate(effects):
            item = {"i": i, "type": e["type"], "text": e.get("text", ""), "x": float(e.get("x", 0.5)),
                    "y": float(e.get("y", 0.5)), "placed": bool(e.get("placed")), "auto": False,
                    "t": None, "word": "", "measured": None}
            if e["type"] == "text":
                item["angle"] = tilt_for(project.data.get("seed", 0), sc["number"], i) \
                    if style.get("text_style") == "hand_underline" else 0.0
                if placer and not e.get("placed"):
                    pos = placer.place(si, sc, item)
                    if pos:
                        item["x"], item["y"], item["auto"] = pos[0], pos[1], True
            if sw:
                w = sw[min(int(e.get("word", 0)), len(sw) - 1)]
                item.update(t=float(w["s"]), word=w["text"], measured=bool(w.get("m", True)))
            items.append(item)
        if placer:
            placer.save()
        out[sc["number"]] = items
    return out


# ---------------------------------------------------------------------------------------------- easing
def _ease_out_back(q):
    c1 = 1.70158
    c3 = c1 + 1
    q = min(1.0, max(0.0, q))
    return 1 + c3 * (q - 1) ** 3 + c1 * (q - 1) ** 2


def _ease_out(q):
    q = min(1.0, max(0.0, q))
    return 1 - (1 - q) ** 3


# ---------------------------------------------------------------------------------------------- sprites
def _to_premult(rgba_img):
    """PIL RGBA -> float32 premultiplied BGRA array (0..1)."""
    a = np.asarray(rgba_img).astype(np.float32) / 255.0
    out = np.empty_like(a)
    out[..., :3] = a[..., 2::-1] * a[..., 3:4]
    out[..., 3] = a[..., 3]
    return out


def pin_sprite(color, height):
    """Classic map pin, drawn big and scaled down. Returns (sprite, anchor at the tip)."""
    h = max(12, int(round(height)))
    w = int(round(h * 0.72))
    pad = max(2, h // 16)
    W, H = (w + 2 * pad) * SS, (h + 2 * pad) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = w * SS / 2
    cx, cy = W / 2, pad * SS + r
    tip = (W / 2, H - pad * SS)
    rgb = hex_to_rgb(color, (229, 57, 53))
    dark = tuple(int(c * 0.62) for c in rgb)
    # body: circle + the two tangent lines down to the tip
    dist = tip[1] - cy
    ang = math.asin(min(0.999, r / dist))
    t1 = (cx - r * math.cos(ang), cy + r * math.sin(ang))
    t2 = (cx + r * math.cos(ang), cy + r * math.sin(ang))
    edge = max(1, int(SS * h / 40))
    # dark outline first (slightly bigger), then the coloured body on top
    d.ellipse([cx - r - edge, cy - r - edge, cx + r + edge, cy + r + edge], fill=dark + (255,))
    d.polygon([(t1[0] - edge, t1[1]), (t2[0] + edge, t2[1]), (tip[0], tip[1])], fill=dark + (255,))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb + (255,))
    d.polygon([t1, t2, (tip[0], tip[1] - edge * 1.6)], fill=rgb + (255,))
    # inner white dot and a soft highlight
    ri = r * 0.38
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=(255, 255, 255, 255))
    hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([cx - r * 0.75, cy - r * 0.85, cx - r * 0.05, cy - r * 0.2], fill=(255, 255, 255, 70))
    hl = hl.filter(ImageFilter.GaussianBlur(r * 0.15))
    img = Image.alpha_composite(img, Image.composite(hl, Image.new("RGBA", (W, H), (0, 0, 0, 0)), img.split()[3]))
    img = img.resize((W // SS, H // SS), Image.LANCZOS)
    return _to_premult(img), (W / SS / 2, (H - pad * SS) / SS)


def shadow_sprite(width):
    w = max(8, int(round(width)))
    h = max(4, int(round(width * 0.28)))
    pad = int(w * 0.3)
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([pad, pad, pad + w, pad + h], fill=(0, 0, 0, 150))
    img = img.filter(ImageFilter.GaussianBlur(max(1, w * 0.08)))
    return _to_premult(img), ((w + 2 * pad) / 2, (h + 2 * pad) / 2)


def text_sprite(text, font_name, size, color, outline_color, outline, box, box_color, anchor="center"):
    font = fonts.load(font_name, max(8, int(size)))
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=outline)
    tw, th = r - l, b - t
    padx = int(size * 0.35) if box else outline + 4
    pady = int(size * 0.22) if box else outline + 4
    W, H = tw + 2 * padx, th + 2 * pady
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if box:
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=int(size * 0.22), fill=hex_to_rgb(box_color, (0, 0, 0)) + (178,))
    d.text((padx - l, pady - t), text, font=font, fill=hex_to_rgb(color) + (255,), stroke_width=outline,
           stroke_fill=hex_to_rgb(outline_color, (0, 0, 0)) + (255,))
    spr = _to_premult(img)
    return spr, ((W / 2, H / 2) if anchor == "center" else (0.0, H / 2))


# ---------------------------------------------------------------------------------------------- drawing
def blit(frame, sprite, anchor, X, Y, scale=1.0, opacity=1.0, angle=0.0):
    """Composite a premultiplied BGRA sprite onto a BGR uint8 frame with sub-pixel accuracy.

    (X, Y) is where the sprite's anchor point lands, in frame pixel-edge coordinates. `angle` rotates the
    sprite around its anchor (degrees, positive = clockwise on screen).
    """
    if opacity <= 0.003 or scale <= 0.01:
        return
    Hf, Wf = frame.shape[:2]
    sh, sw = sprite.shape[:2]
    ax, ay = anchor
    th = math.radians(angle)
    c, s_ = math.cos(th) * scale, math.sin(th) * scale
    R = np.array([[c, -s_], [s_, c]])
    corners = np.array([[0, 0], [sw, 0], [0, sh], [sw, sh]], dtype=np.float64) - [ax, ay]
    pts = corners @ R.T + [X, Y]
    x0, y0 = int(math.floor(pts[:, 0].min())) - 2, int(math.floor(pts[:, 1].min())) - 2
    x1, y1 = int(math.ceil(pts[:, 0].max())) + 2, int(math.ceil(pts[:, 1].max())) + 2
    rx0, ry0, rx1, ry1 = max(0, x0), max(0, y0), min(Wf, x1), min(Hf, y1)
    if rx1 <= rx0 or ry1 <= ry0:
        return
    # pixel centres: dst + 0.5 = R (src + 0.5 - anchor) + (X, Y)
    t = R @ (np.array([0.5, 0.5]) - [ax, ay]) + [X - 0.5 - rx0, Y - 0.5 - ry0]
    M = np.array([[R[0, 0], R[0, 1], t[0]], [R[1, 0], R[1, 1], t[1]]], dtype=np.float64)
    part = cv2.warpAffine(sprite, M, (rx1 - rx0, ry1 - ry0), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = part[..., 3:4] * opacity
    roi = frame[ry0:ry1, rx0:rx1].astype(np.float32)
    out = roi * (1.0 - a) + part[..., :3] * (255.0 * opacity)
    frame[ry0:ry1, rx0:rx1] = np.clip(out + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------- hand-lettered text
def _disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _layer(mask, rgb):
    """Coverage mask (float 0..1) + colour -> premultiplied BGRA."""
    out = np.zeros(mask.shape + (4,), np.float32)
    for i, v in enumerate(rgb[::-1]):
        out[..., i] = mask * (v / 255.0)
    out[..., 3] = mask
    return out


def _over(top, bottom):
    return top + bottom * (1.0 - top[..., 3:4])


def hand_text_sprite(text, font_name, size, ink="#262523", halo="#F5F2EA", line="#C34D48", seed="",
                     weight=0.02, halo_width=0.17, underline=True, tracking=0.07):
    """Hand-lettered comic caption: CAPITALS, every letter slightly rotated / lifted like inked by hand,
    thickened strokes, a thick sticker-like halo, an almost invisible shadow and a red marker underline.

    Returns {"text": sprite, "line": sprite (same canvas), "anchor": (cx, cy), "line_x": (x0, x1), "feather": px}.
    """
    import random
    text = " ".join(text.upper().split())
    big = max(10, int(round(size * SS)))
    font = fonts.load(font_name, big)
    hb = font.getbbox("H")
    cap = max(4, hb[3] - hb[1])
    asc, desc = font.getmetrics()
    rng = random.Random(f"hand:{seed}:{text}")
    wpx, hpx = weight * cap, halo_width * cap
    pad = int(hpx + weight * cap + cap * 0.6) + 4
    track = tracking * cap  # letter-spacing, like hand lettering
    total = font.getlength(text) + track * max(0, len(text) - 1)
    Wc, Hc = int(total + 2 * pad), int(asc + desc + 2 * pad + cap * 0.35)
    mask = np.zeros((Hc, Wc), np.float32)
    first_left = last_right = None
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        x = pad + font.getlength(text[:i]) + track * i  # includes kerning with the previous letters
        g = Image.new("L", (int(font.getlength(ch) + cap), int(asc + desc + cap)), 0)
        ImageDraw.Draw(g).text((cap / 2, cap / 2), ch, font=font, fill=255)
        g = g.rotate(rng.uniform(-3.0, 3.0), resample=Image.BICUBIC, center=(g.width / 2, cap / 2 + asc * 0.6))
        dy = rng.uniform(-0.035, 0.035) * cap
        gx, gy = int(round(x - cap / 2)), int(round(pad - cap / 2 + dy))
        arr = np.asarray(g, np.float32) / 255.0
        h, w = arr.shape
        ys, xs = max(0, gy), max(0, gx)
        sub = arr[ys - gy:ys - gy + min(h, Hc - ys), xs - gx:xs - gx + min(w, Wc - xs)]
        mask[ys:ys + sub.shape[0], xs:xs + sub.shape[1]] = np.maximum(mask[ys:ys + sub.shape[0], xs:xs + sub.shape[1]], sub)
        l, _t, r, _b = font.getbbox(ch)
        first_left = x + l if first_left is None else first_left
        last_right = x + r
    ink_m = cv2.dilate(mask, _disk(wpx)) if wpx >= 1 else mask                 # bolder, rounder strokes
    halo_m = cv2.GaussianBlur(cv2.dilate(ink_m, _disk(hpx)), (0, 0), SS * 0.7)  # sticker halo
    shadow_m = np.roll(cv2.GaussianBlur(halo_m, (0, 0), cap * 0.10), int(cap * 0.05), axis=0) * 0.16
    out = _over(_layer(ink_m, hex_to_rgb(ink, (38, 37, 35))), _layer(halo_m, hex_to_rgb(halo, (245, 242, 234))))
    out = _over(out, _layer(shadow_m, (0, 0, 0)))
    baseline = pad + asc
    line_img = np.zeros_like(out)
    lx0 = lx1 = 0.0
    if underline and first_left is not None:
        lx0, lx1 = first_left - cap * 0.05, last_right + cap * 0.18      # under the first letter .. just past the last
        y0 = baseline + cap * 0.17
        n = 160
        xs_ = np.linspace(lx0, lx1, n)
        u = (xs_ - lx0) / max(1.0, lx1 - lx0)
        ph1, ph2 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
        wave = cap * (0.035 * np.sin(2 * np.pi * 1.1 * u + ph1) + 0.015 * np.sin(2 * np.pi * 3.3 * u + ph2))
        ys_ = y0 + wave + cap * rng.uniform(-0.04, 0.04) * (u - 0.5)
        thick = cap * 0.13 * (0.5 + 0.5 * np.sin(np.pi * u) ** 0.6)      # thicker in the middle, tapered ends
        dx, dy = np.gradient(xs_), np.gradient(ys_)
        nl = np.hypot(dx, dy)
        nx, ny = -dy / nl, dx / nl
        upper = np.stack([xs_ + nx * thick / 2, ys_ + ny * thick / 2], 1)
        lower = np.stack([xs_ - nx * thick / 2, ys_ - ny * thick / 2], 1)[::-1]
        lm = np.zeros((Hc, Wc), np.uint8)
        poly = np.concatenate([upper, lower]).astype(np.int32)
        cv2.fillPoly(lm, [poly], 255, cv2.LINE_AA)
        for k in (0, n - 1):  # round marker ends
            cv2.circle(lm, (int(xs_[k]), int(ys_[k])), max(1, int(thick[k] / 2)), 255, -1, cv2.LINE_AA)
        line_m = lm.astype(np.float32) / 255.0 * 0.96
        line_img = _layer(line_m, hex_to_rgb(line, (195, 77, 72)))
    # back to output resolution
    small = (max(1, Wc // SS), max(1, Hc // SS))
    text_s = cv2.resize(out, small, interpolation=cv2.INTER_AREA)
    line_s = cv2.resize(line_img, small, interpolation=cv2.INTER_AREA)
    bbox_x0, bbox_x1 = (first_left or pad) / SS, (last_right or pad) / SS
    anchor = ((bbox_x0 + bbox_x1) / 2, (pad + asc - cap / 2) / SS)
    return {"text": text_s, "line": line_s, "anchor": anchor, "line_x": (lx0 / SS, lx1 / SS),
            "feather": max(1.5, cap * 0.08 / SS), "cap": cap / SS,
            "extent": _extent(np.maximum(text_s[..., 3], line_s[..., 3]), anchor)}


def _extent(alpha, anchor):
    """Tight box around the visible pixels, relative to the anchor: (left, top, right, bottom) in px."""
    ys, xs = np.nonzero(alpha > 0.04)
    if not len(xs):
        return (0.0, 0.0, 0.0, 0.0)
    return (float(xs.min() - anchor[0]), float(ys.min() - anchor[1]), float(xs.max() + 1 - anchor[0]),
            float(ys.max() + 1 - anchor[1]))


def rotated_extent(ext, angle):
    """Extent of a box after rotating it around the anchor by `angle` degrees."""
    th = math.radians(angle)
    c, s_ = math.cos(th), math.sin(th)
    l, t, r, b = ext
    pts = [(x * c - y * s_, x * s_ + y * c) for x, y in ((l, t), (r, t), (l, b), (r, b))]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def line_progress(line, x0, x1, p, feather):
    """The underline drawn up to fraction p (0..1), left to right, with a soft leading edge."""
    if p >= 1:
        return line
    xp = x0 + (x1 - x0) * max(0.0, p)
    xs = np.arange(line.shape[1], dtype=np.float32) + 0.5
    ramp = np.clip((xp - xs) / feather + 0.5, 0, 1)
    return line * ramp[None, :, None]


def ring(frame, X, Y, radius, thickness, color_bgr, opacity):
    if opacity <= 0.003 or radius < 1:
        return
    Hf, Wf = frame.shape[:2]
    m = int(radius + thickness + 3)
    x0, y0, x1, y1 = max(0, int(X) - m), max(0, int(Y) - m), min(Wf, int(X) + m + 1), min(Hf, int(Y) + m + 1)
    if x1 <= x0 or y1 <= y0:
        return
    roi = frame[y0:y1, x0:x1]
    layer = roi.copy()
    sh = 4  # cv2 fixed-point: 4 fractional bits -> 1/16 pixel precision
    c = (int(round((X - 0.5 - x0) * 16)), int(round((Y - 0.5 - y0) * 16)))
    cv2.ellipse(layer, c, (int(round(radius * 16)), int(round(radius * 0.42 * 16))), 0, 0, 360, color_bgr,
                max(1, int(round(thickness))), cv2.LINE_AA, sh)
    cv2.addWeighted(layer, opacity, roi, 1 - opacity, 0, dst=roi)


class EffectLayer:
    """Draws one scene's effects onto its frames."""

    def __init__(self, effects, style, W, H, fps, ext_start_frame):
        self.fx = effects
        self.st = {**DEFAULT_STYLE, **(style or {})}
        self.W, self.H, self.fps, self.e0 = W, H, fps, ext_start_frame
        unit = min(W, H) / 1080.0
        st = self.st
        self.pin_h = float(st["pin_size"]) * unit
        # pins are drawn 30 % larger and scaled down, so they stay crisp while the camera zooms in
        self.pin, self.pin_anchor = pin_sprite(st["pin_color"], self.pin_h * 1.3)
        self.shadow, self.shadow_anchor = shadow_sprite(self.pin_h * 0.72 * 1.3)
        self.pin_bgr = tuple(int(c) for c in hex_to_rgb(st["pin_color"])[::-1])
        self.texts = {}
        self.hand = {}
        for e in effects:
            if e["type"] == "text" and st.get("text_style") == "hand_underline":
                self.hand[e["i"]] = hand_layers(e["text"], st, W, H, seed=e["i"])
            elif e["type"] == "text":
                self.texts[e["i"]] = text_sprite(e["text"], st["text_font"], float(st["text_size"]) * unit,
                                                 st["text_color"], st["text_outline_color"],
                                                 max(0, int(round(float(st["text_outline"]) * unit))),
                                                 bool(st["text_box"]), st["box_color"])
            elif e["type"] == "pin" and e.get("text"):
                self.texts[e["i"]] = text_sprite(e["text"], st["text_font"], float(st["label_size"]) * unit,
                                                 st["text_color"], st["text_outline_color"],
                                                 max(0, int(round(float(st["text_outline"]) * unit * 0.6))),
                                                 bool(st["text_box"]), st["box_color"], anchor="left")

    def draw(self, frame, k, project):
        """k = local frame index in the scene's extended range; project(k, fx, fy) -> (X, Y, zoom)."""
        t_now = (self.e0 + k) / self.fps
        for e in self.fx:
            t = t_now - e["t"]
            if e["type"] == "pin":
                if t < -FALL:
                    continue
                X, Y, z = project(k, e["x"], e["y"])
                self._pin(frame, e, t, X, Y, z)
            else:
                if t < 0:
                    continue
                X, Y, _z = project(k, e["x"], e["y"])
                if e["i"] in self.hand:
                    self._hand(frame, e, t, X, Y)
                    continue
                spr, anc = self.texts[e["i"]]
                X, Y = self._keep_inside(X, Y, (-anc[0], -anc[1], spr.shape[1] - anc[0], spr.shape[0] - anc[1]), 0.0)
                q = t / TEXT_POP
                blit(frame, spr, anc, X, Y, scale=0.55 + 0.45 * _ease_out_back(q), opacity=min(1.0, t / 0.08))

    def _keep_inside(self, X, Y, ext, angle):
        """Shift text (its anchor at X, Y; tight extent `ext`) just enough to stay inside the safe margins."""
        l, t, r, b = rotated_extent(ext, angle)
        mx, my = SAFE * self.W, SAFE * self.H
        X = min(max(X, mx - l), self.W - mx - r) if (r - l) + 2 * mx < self.W else self.W / 2 - (l + r) / 2
        Y = min(max(Y, my - t), self.H - my - b) if (b - t) + 2 * my < self.H else self.H / 2 - (t + b) / 2
        return X, Y

    def _hand(self, frame, e, t, X, Y):
        L = self.hand[e["i"]]
        ang = float(e.get("angle", 0.0))
        X, Y = self._keep_inside(X, Y, L["extent"], ang)
        q = _ease_out(t / HAND_IN)
        scale = 0.9 + 0.1 * q          # calm: 90 % -> 100 %, no bounce
        blit(frame, L["text"], L["anchor"], X, Y, scale=scale, opacity=min(1.0, t / (HAND_IN * 0.8)), angle=ang)
        if L["has_line"] and t >= LINE_DELAY:
            p = (t - LINE_DELAY) / LINE_DRAW
            p = p * p * (3 - 2 * p) if p < 1 else 1.0
            line = line_progress(L["line"], L["line_x"][0], L["line_x"][1], p, L["feather"])
            blit(frame, line, L["anchor"], X, Y, scale=scale, angle=ang)

    def _pin(self, frame, e, t, X, Y, z):
        s = z / 1.3  # sprite was drawn 1.3x
        ph = self.pin_h * z
        if t < 0:
            p = (t + FALL) / FALL
            drop = min(Y + ph * 1.2, 0.38 * self.H)
            off = -drop * (1 - p * p)          # accelerates like a falling object
            alpha = min(1.0, p / 0.25)
            blit(frame, self.shadow, self.shadow_anchor, X, Y, scale=s * (0.45 + 0.55 * p), opacity=0.3 + 0.45 * p)
        else:
            if t < BOUNCE:
                off = -0.18 * ph * math.sin(math.pi * t / BOUNCE)
            elif t < BOUNCE + 0.14:
                off = -0.05 * ph * math.sin(math.pi * (t - BOUNCE) / 0.14)
            else:
                off = 0.0
            alpha = 1.0
            blit(frame, self.shadow, self.shadow_anchor, X, Y, scale=s * (1.0 + off / ph * 0.8), opacity=0.75)
            if t < RIPPLE:
                q = t / RIPPLE
                radius = self.pin_h * z * 0.72 * (0.25 + 1.4 * _ease_out(q))
                ring(frame, X, Y, radius, max(1.5, ph * 0.05 * (1 - q) + 1), self.pin_bgr, 0.85 * (1 - q))
        blit(frame, self.pin, self.pin_anchor, X, Y + off, scale=s, opacity=alpha)
        if e["i"] in self.texts and t >= LABEL_DELAY:
            q = min(1.0, (t - LABEL_DELAY) / 0.2)
            spr, anc = self.texts[e["i"]]
            lx = X + ph * 0.42 - (1 - _ease_out(q)) * ph * 0.3
            ly = Y - ph * 0.72
            blit(frame, spr, anc, lx, ly, scale=1.0, opacity=q)


# ---------------------------------------------------------------------------------------------- sounds
SOUND_KINDS = ("pin", "text", "underline")


def sounds_dir():
    from . import paths
    d = paths.SETTINGS_DIR / "sounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sound_settings():
    """{"pin": {"path": Path or None, "name": str, "volume": float}, "text": {...}} - shared by all projects."""
    from . import paths
    cfg = paths.load_app_settings().get("effect_sounds", {})
    out = {}
    for kind in SOUND_KINDS:
        c = cfg.get(kind, {})
        f = sounds_dir() / c["file"] if c.get("file") else None
        out[kind] = {"path": f if f and f.exists() else None, "name": c.get("name", ""),
                     "volume": float(c.get("volume", 0.8))}
    return out


def save_sound_settings(kind, **changes):
    from . import paths
    data = paths.load_app_settings()
    cfg = data.setdefault("effect_sounds", {})
    cfg.setdefault(kind, {}).update(changes)
    paths.save_app_settings(data)


# ---------------------------------------------------------------------------------------------- hand style layers
def hand_layers(text, st, W, H, seed=""):
    """Hand-lettered text + underline sprites for a W x H frame. Long text shrinks to fit the safe area."""
    unit = min(W, H) / 1080.0
    size = float(st.get("hand_size", 150)) * unit
    for _ in range(4):
        L = hand_text_sprite(text, st.get("hand_font", "Itim"), size, ink=st.get("hand_color", "#262523"),
                             halo=st.get("hand_halo", "#F5F2EA"), line=st.get("underline_color", "#C34D48"),
                             seed=seed, underline=bool(st.get("underline", True)))
        maxw = W * (1 - 2 * SAFE) * 0.94
        width = L["extent"][2] - L["extent"][0]
        if width <= maxw:
            break
        size *= maxw / width
    L["has_line"] = bool(st.get("underline", True))
    return L


def text_box_px(text, st, W, H):
    """Tight extent (left, top, right, bottom) in pixels around its position that a [TEXT] takes in a W x H frame."""
    if st.get("text_style") == "hand_underline":
        return hand_layers(text, st, W, H)["extent"]
    unit = min(W, H) / 1080.0
    spr, _a = text_sprite(text, st["text_font"], float(st["text_size"]) * unit, st["text_color"],
                          st["text_outline_color"], max(0, int(round(float(st["text_outline"]) * unit))),
                          bool(st["text_box"]), st["box_color"])
    return (-spr.shape[1] / 2, -spr.shape[0] / 2, spr.shape[1] / 2, spr.shape[0] / 2)


# ---------------------------------------------------------------------------------------------- auto placement
_FACE_NET = None


def _faces(bgr):
    """Face boxes (x, y, w, h) found by OpenCV's YuNet detector (works on photos and most illustrations)."""
    global _FACE_NET
    from pathlib import Path
    model = Path(__file__).resolve().parent / "data" / "face_detection_yunet_2023mar.onnx"
    try:
        h, w = bgr.shape[:2]
        if _FACE_NET is None:
            _FACE_NET = cv2.FaceDetectorYN.create(str(model), "", (w, h), 0.5, 0.3, 5000)
        _FACE_NET.setInputSize((w, h))
        _ok, faces = _FACE_NET.detect(bgr)
        return [] if faces is None else [tuple(float(v) for v in f[:4]) for f in faces]
    except Exception:
        return []


class AutoPlacer:
    """Puts [TEXT] in the emptiest part of a scene's picture (sky, plain background, open ground), away from
    faces, skin and busy detail, preferring the top of the frame, inside safe margins and clear of captions,
    for the whole camera move. Results are cached per picture / text / style."""

    VERSION = 2

    def __init__(self, project, style):
        import json
        self.p, self.st = project, style
        self.file = project.work_dir / "auto_place.json"
        try:
            self.cache = json.loads(self.file.read_text()) if self.file.exists() else {}
        except Exception:
            self.cache = {}
        self.dirty = False
        self._plans = None
        self.taken = {}  # scene index -> boxes already used by earlier texts in that scene
        self.W, self.H = (1080, 1920) if project.data.get("aspect") == "9:16" else (1920, 1080)

    def save(self):
        import json
        if self.dirty:
            self.file.write_text(json.dumps(self.cache))
            self.dirty = False

    def plans(self):
        if self._plans is None:
            from .media import media_kind
            from .motion import plan_motions
            nums = [s["number"] for s in self.p.scenes]
            imgs = {s["number"] for s in self.p.scenes if media_kind(self.p.path(s.get("media")) or "") != "video"}
            self._plans = plan_motions(nums, imgs, self.p.settings, self.p.data["seed"])
        return self._plans

    def place(self, si, sc, item):
        import hashlib
        import json
        from .media import media_kind
        mp = self.p.path(sc.get("media"))
        if not mp or not mp.exists():
            return None
        st_ = mp.stat()
        kind = media_kind(mp)
        plan = self.plans().get(sc["number"]) if kind != "video" else None
        cap = self.p.settings.get("captions", {})
        keys = ("text_style", "hand_font", "hand_size", "underline", "text_font", "text_size", "text_outline", "text_box")
        sig = json.dumps([self.VERSION, str(mp), st_.st_size, int(st_.st_mtime), item["text"], item.get("angle", 0),
                          {k: self.st.get(k) for k in keys}, self.W, self.H, plan,
                          bool(cap.get("enabled")), cap.get("position"), self.taken.get(si, [])],
                         sort_keys=True, default=str)
        key = hashlib.sha1(sig.encode()).hexdigest()[:20]
        # several texts in one scene: avoid the ones already placed
        key += f"-{item['i']}"
        if key not in self.cache:
            self.cache[key] = self._compute(mp, kind, plan, item, cap, self.taken.get(si, []))
            self.dirty = True
        x, y, bw, bh, cx, cy = self.cache[key]
        self.taken.setdefault(si, []).append([cx, cy, bw, bh])
        return x, y

    def _picture(self, mp, kind):
        from .sources import load_image_rgb
        if kind == "video":
            from . import ffmpeg_utils as ff
            import subprocess
            dur = ff.duration(mp)
            proc = ff.popen(["-ss", f"{min(1.0, dur / 2):.2f}", "-i", str(mp), "-frames:v", "1", "-vf", "scale=640:-2",
                             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
            raw, _ = proc.communicate()
            info = ff.video_info(mp)
            h = int(round(640 * info["height"] / max(1, info["width"]) / 2) * 2)
            return np.frombuffer(raw, np.uint8)[:640 * h * 3].reshape(h, 640, 3).copy()
        rgb = load_image_rgb(mp)
        s = 640 / max(rgb.shape[1], 1)
        return cv2.resize(rgb, (640, max(2, int(rgb.shape[0] * s))), interpolation=cv2.INTER_AREA)[:, :, ::-1].copy()

    def _visible(self, a, plan):
        """Part of the picture (fractions) that is in frame during the WHOLE camera move."""
        from .motion import camera_at
        A = self.W / self.H
        fw0, fh0 = (A / a, 1.0) if a > A else (1.0, a / A)
        L, T, R, B = 0.0, 0.0, 1.0, 1.0
        samples = [None] if not plan else [i / 8 for i in range(9)]
        for p in samples:
            z, xo, yo = (1.0, 0.0, 0.0) if p is None else camera_at(plan, p)
            w, h = fw0 / z, fh0 / z
            cx = min(max(0.5 + xo * fw0, w / 2), 1 - w / 2)
            cy = min(max(0.5 + yo * fh0, h / 2), 1 - h / 2)
            L, T, R, B = max(L, cx - w / 2), max(T, cy - h / 2), min(R, cx + w / 2), min(B, cy + h / 2)
        return (L, T, R, B), fw0, fh0

    def _compute(self, mp, kind, plan, item, cap, taken=()):
        bgr = self._picture(mp, kind)
        ph, pw = bgr.shape[:2]
        (L, T, R, B), fw0, fh0 = self._visible(pw / ph, plan)
        l, t, r, b = rotated_extent(text_box_px(item["text"], self.st, self.W, self.H), float(item.get("angle", 0.0)))
        # extents in picture fractions (at the widest camera view, where the text covers the most picture)
        l, r = l / self.W * fw0, r / self.W * fw0
        t, b = t / self.H * fh0, b / self.H * fh0
        bw, bh = r - l, b - t
        mx, my = SAFE * fw0, SAFE * fh0
        x_lo, x_hi = L + mx - l, R - mx - r
        y_lo, y_hi = T + my - t, B - my - b
        # keep clear of the captions band
        if cap.get("enabled", True):
            pos = cap.get("position", "bottom")
            fh = B - T
            band = {"bottom": (0.70, 1.0), "middle": (0.36, 0.64), "top": (0.0, 0.28)}.get(pos, (0.70, 1.0))
            if pos == "bottom":
                y_hi = min(y_hi, T + band[0] * fh - b)
            elif pos == "top":
                y_lo = max(y_lo, T + band[1] * fh - t)
        if x_lo > x_hi:
            x_lo = x_hi = (L + R) / 2 - (l + r) / 2
        if y_lo > y_hi:
            y_hi = y_lo
        # cost maps: busy detail, skin, faces
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mag = np.hypot(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
        busy = cv2.GaussianBlur(mag, (0, 0), 3)
        busy = np.clip(busy / (np.percentile(busy, 95) + 1e-6), 0, 1)
        ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        skin = ((ycc[..., 1] > 135) & (ycc[..., 1] < 175) & (ycc[..., 2] > 80) & (ycc[..., 2] < 125)).astype(np.float32)
        skin = cv2.GaussianBlur(skin, (0, 0), 4)
        face = np.zeros_like(gray)
        for x, y, w, h in _faces(bgr):
            # the face plus the body below it
            cv2.rectangle(face, (int(x - 0.5 * w), int(y - 0.6 * h)), (int(x + 1.5 * w), int(y + 3.0 * h)), 1.0, -1)
        for x, y, w, h in taken:  # other texts in this scene (their centre + size)
            cv2.rectangle(face, (int((x - w / 2) * pw), int((y - h / 2) * ph)), (int((x + w / 2) * pw), int((y + h / 2) * ph)), 1.0, -1)
        cost = busy + 0.8 * skin + 3.0 * face
        ii = cv2.integral(cost)
        best, best_xy = None, ((x_lo + x_hi) / 2, y_lo)
        bwp, bhp = max(2, int(bw * pw)), max(2, int(bh * ph))
        for gy in np.linspace(y_lo, y_hi, 24):
            for gx in np.linspace(x_lo, x_hi, 32):
                x0, y0 = int((gx + l) * pw), int((gy + t) * ph)
                x0, y0 = min(max(0, x0), pw - bwp), min(max(0, y0), ph - bhp)
                x1, y1 = x0 + bwp, y0 + bhp
                mean = (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / (bwp * bhp)
                vpos = (gy - y_lo) / (y_hi - y_lo) if y_hi > y_lo else 0.0
                c = mean + 0.25 * vpos + 0.08 * abs(gx - (L + R) / 2) / max(1e-6, R - L)  # prefer the top, then centre
                if best is None or c < best:
                    best, best_xy = c, (gx, gy)
        # remember the box (centre + size) so a second text in the scene avoids it
        return [round(float(best_xy[0]), 4), round(float(best_xy[1]), 4), round(bw, 4), round(bh, 4),
                round(float(best_xy[0] + (l + r) / 2), 4), round(float(best_xy[1] + (t + b) / 2), 4)]
