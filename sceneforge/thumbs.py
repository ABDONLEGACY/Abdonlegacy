"""Small thumbnails of each scene's media for the review table."""
import base64
from pathlib import Path

from PIL import Image, ImageOps

from . import ffmpeg_utils as ff
from .media import media_kind

SIZE = (160, 90)


def thumbnail(project, media_rel):
    """Return a JPEG thumbnail path for a media file (cached in work/thumbs)."""
    src = project.path(media_rel)
    if not src or not src.exists():
        return None
    st = src.stat()
    out_dir = project.work_dir / "thumbs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.stem}_{st.st_size}_{int(st.st_mtime)}.jpg"
    if out.exists():
        return out
    try:
        if media_kind(src) == "video":
            tmp = out.with_suffix(".full.jpg")
            dur = ff.duration(src)
            ff.run(["-ss", f"{min(1.0, dur / 2):.2f}", "-i", str(src), "-frames:v", "1", "-q:v", "4", str(tmp)],
                   desc="thumbnail")
            img = Image.open(tmp)
        else:
            img = ImageOps.exif_transpose(Image.open(src))
        img = ImageOps.fit(img.convert("RGB"), SIZE)
        img.save(out, quality=80)
        if media_kind(src) == "video":
            tmp.unlink(missing_ok=True)
    except Exception:
        return None
    return out


def data_uri(path):
    if not path:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
