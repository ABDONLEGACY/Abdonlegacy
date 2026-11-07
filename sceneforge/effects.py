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
SS = 4           # supersampling when drawing sprites, for smooth edges

DEFAULT_STYLE = {
    "pin_color": "#E53935", "pin_size": 90,
    "text_font": "Arial Bold", "text_size": 96, "text_color": "#FFFFFF",
    "text_outline_color": "#000000", "text_outline": 6, "text_box": False, "box_color": "#000000",
    "label_size": 44,
}


# ---------------------------------------------------------------------------------------------- timing
def resolve(project, words=None):
    """{scene number: [effect, ...]} with each effect's trigger time "t" (seconds, from the audio)."""
    words = project.words() if words is None else words
    by_scene = {}
    for w in words:
        by_scene.setdefault(w["scene"], []).append(w)
    out = {}
    for si, sc in enumerate(project.scenes):
        effects = sc.get("effects") or []
        if not effects:
            continue
        sw = by_scene.get(si, [])
        items = []
        for i, e in enumerate(effects):
            if not sw:
                continue
            k = min(int(e.get("word", 0)), len(sw) - 1)
            w = sw[k]
            items.append({"i": i, "type": e["type"], "text": e.get("text", ""), "x": float(e.get("x", 0.5)),
                          "y": float(e.get("y", 0.5)), "t": float(w["s"]), "word": w["text"],
                          "measured": bool(w.get("m", True))})
        if items:
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
def blit(frame, sprite, anchor, X, Y, scale=1.0, opacity=1.0):
    """Composite a premultiplied BGRA sprite onto a BGR uint8 frame with sub-pixel accuracy.

    (X, Y) is where the sprite's anchor point lands, in frame pixel-edge coordinates.
    """
    if opacity <= 0.003 or scale <= 0.01:
        return
    Hf, Wf = frame.shape[:2]
    sh, sw = sprite.shape[:2]
    ax, ay = anchor
    x0 = int(math.floor(X - scale * ax)) - 2
    y0 = int(math.floor(Y - scale * ay)) - 2
    x1 = int(math.ceil(X + scale * (sw - ax))) + 2
    y1 = int(math.ceil(Y + scale * (sh - ay))) + 2
    rx0, ry0, rx1, ry1 = max(0, x0), max(0, y0), min(Wf, x1), min(Hf, y1)
    if rx1 <= rx0 or ry1 <= ry0:
        return
    M = np.array([[scale, 0, scale * (0.5 - ax) + X - 0.5 - rx0],
                  [0, scale, scale * (0.5 - ay) + Y - 0.5 - ry0]], dtype=np.float64)
    part = cv2.warpAffine(sprite, M, (rx1 - rx0, ry1 - ry0), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = part[..., 3:4] * opacity
    roi = frame[ry0:ry1, rx0:rx1].astype(np.float32)
    out = roi * (1.0 - a) + part[..., :3] * (255.0 * opacity)
    frame[ry0:ry1, rx0:rx1] = np.clip(out + 0.5, 0, 255).astype(np.uint8)


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
        for e in effects:
            if e["type"] == "text":
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
                spr, anc = self.texts[e["i"]]
                q = t / TEXT_POP
                blit(frame, spr, anc, X, Y, scale=0.55 + 0.45 * _ease_out_back(q), opacity=min(1.0, t / 0.08))

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
SOUND_KINDS = ("pin", "text")


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
