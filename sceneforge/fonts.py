"""Find fonts installed on this computer (and in SceneForge's own 'fonts' folder)."""
import os
from pathlib import Path

from PIL import ImageFont

from . import paths

_CACHE = None

FALLBACKS = {
    "arial bold": ["Arial Bold", "Liberation Sans Bold", "DejaVu Sans Bold"],
    "arial": ["Arial", "Liberation Sans", "DejaVu Sans"],
}


def _font_dirs():
    dirs = [paths.FONTS_DIR]
    if paths.IS_WINDOWS:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts",
                 Path("/Library/Fonts"), Path("/System/Library/Fonts")]
    return [d for d in dirs if d.is_dir()]


def list_fonts():
    """{display name: file path}, e.g. {"Arial Bold": "C:/Windows/Fonts/arialbd.ttf"}."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    found = {}
    for d in _font_dirs():
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() not in (".ttf", ".otf"):
                continue
            try:
                fam, style = ImageFont.truetype(str(f), 20).getname()
            except Exception:
                continue
            if not fam:
                continue
            style = (style or "").strip()
            name = fam if style.lower() in ("", "regular", "normal", "book", "roman") else f"{fam} {style}"
            found.setdefault(name, str(f))
    _CACHE = dict(sorted(found.items(), key=lambda kv: kv[0].lower()))
    return _CACHE


def resolve(name):
    """Return a font file path for a display name, with sensible fallbacks."""
    fonts = list_fonts()
    if name in fonts:
        return fonts[name]
    if name and Path(name).is_file():
        return name
    low = {k.lower(): v for k, v in fonts.items()}
    if name and name.lower() in low:
        return low[name.lower()]
    for cand in FALLBACKS.get((name or "").lower(), []) + FALLBACKS["arial bold"]:
        if cand in fonts:
            return fonts[cand]
    bold = [v for k, v in fonts.items() if "bold" in k.lower()]
    if bold:
        return bold[0]
    if fonts:
        return next(iter(fonts.values()))
    return None


def load(name, size):
    path = resolve(name)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)
