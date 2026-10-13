"""Local web server for the SceneForge studio (http://127.0.0.1:7860). Listens on this computer only."""
import os
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import fonts, paths, pipeline, presets, render, script_parser, thumbs
from .media import AUDIO_EXT, media_kind
from .project import Project
from .render import Renderer
from .transcribe import MODEL_CHOICES

WEB_DIR = paths.APP_DIR / "web"
app = FastAPI(title="SceneForge", docs_url=None, redoc_url=None, openapi_url=None)


class UserError(Exception):
    pass


@app.exception_handler(UserError)
async def _user_error(_req, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(ValueError)
async def _value_error(_req, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


# ------------------------------------------------------------------------------------------------ jobs
JOBS = {}
_JOB_LOCK = threading.Lock()


def _running_job():
    return next((j for j in JOBS.values() if j["status"] == "running"), None)


def start_job(kind, folder, fn):
    with _JOB_LOCK:
        busy = _running_job()
        if busy:
            raise UserError(f"Please wait - SceneForge is still busy ({busy['kind']} of '{busy['project']}').")
        jid = uuid.uuid4().hex[:10]
        job = {"id": jid, "kind": kind, "project": folder, "status": "running", "progress": 0.0,
               "message": "Starting ...", "result": None, "error": None, "started": time.time()}
        JOBS[jid] = job

    def progress(frac, msg=""):
        job["progress"] = max(0.0, min(1.0, float(frac)))
        if msg:
            job["message"] = msg

    def runner():
        try:
            job["result"] = fn(progress)
            job["status"] = "done"
            job["progress"] = 1.0
        except render.Stopped:
            job["status"] = "stopped"
            job["message"] = "Stopped. Press Render again to continue where it left off."
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            job["status"] = "error"
            job["error"] = str(e)[:2000] or e.__class__.__name__
        job["finished"] = time.time()

    threading.Thread(target=runner, daemon=True).start()
    return job


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.get("/api/jobs")
def current_job():
    return {"job": _running_job()}


@app.post("/api/render/stop")
def stop_render():
    render.STOP.set()
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ helpers
def load(folder) -> Project:
    d = paths.projects_dir() / folder
    if not (d / "project.json").exists() or d.resolve().parent != paths.projects_dir().resolve():
        raise HTTPException(404, "Project not found")
    return Project.open(d)


def save_uploads(files: List[UploadFile]):
    """Store uploaded files in a temp folder (keeping their names); returns (temp dir, paths)."""
    tmp = Path(tempfile.mkdtemp(prefix="sceneforge_up_"))
    out = []
    for i, f in enumerate(files or []):
        name = Path(f.filename or f"file{i}").name  # folder uploads send "folder/name.png"
        dest = tmp / name
        if dest.exists():
            dest = tmp / f"{i}_{name}"
        with open(dest, "wb") as fh:
            shutil.copyfileobj(f.file, fh, 1 << 20)
        out.append(dest)
    return tmp, out


def outputs(p):
    if not p.output_dir.exists():
        return []
    vids = [v for v in p.output_dir.glob("*.mp4") if ".part" not in v.name]
    vids.sort(key=lambda v: v.stat().st_mtime, reverse=True)
    return [{"name": v.name, "path": p.rel(v), "size": v.stat().st_size, "mtime": v.stat().st_mtime} for v in vids]


def state(p: Project):
    d = p.data
    synced = bool(d.get("sync", {}).get("done"))
    tl = {r["number"]: r for r in p.timeline()} if p.scenes else {}
    scenes = []
    for s in p.scenes:
        mp = p.path(s.get("media"))
        has = bool(mp and mp.exists())
        r = tl.get(s["number"], {})
        scenes.append({
            "number": s["number"], "text": s["text"],
            "start": r.get("start") if synced else None, "end": r.get("end") if synced else None,
            "duration": r.get("duration") if synced else None,
            "auto_start": s.get("auto_start"), "flag": s.get("flag") or "", "confidence": s.get("confidence"),
            "edited": bool(s.get("edited")), "media": Path(s["media"]).name if has else None,
            "media_kind": media_kind(mp) if has else None,
            "media_v": int(mp.stat().st_mtime) if has else 0,
        })
    music, sfx = p.path(d.get("music")), p.path(d.get("sfx"))
    return {
        "folder": p.dir.name, "path": str(p.dir), "name": d["name"], "aspect": d["aspect"], "preset": d["preset"],
        "created": d.get("created"), "settings": p.settings, "audio_duration": d.get("audio_duration") or 0,
        "voice_files": [Path(v).name for v in d.get("voice_files", [])], "script_text": d.get("script_text", ""),
        "expected": d.get("expected_scenes"), "synced": synced, "sync": d.get("sync", {}), "scenes": scenes,
        "missing": [s["number"] for s in scenes if not s["media"]],
        "flagged": [s["number"] for s in scenes if s["flag"]],
        "music": music.name if music and music.exists() else None,
        "sfx": sfx.name if sfx and sfx.exists() else None,
        "render": d.get("render", {}), "outputs": outputs(p),
    }


# ------------------------------------------------------------------------------------------------ projects
class NewProject(BaseModel):
    name: str
    aspect: str = "16:9"
    preset: Optional[str] = None


@app.get("/api/projects")
def list_projects():
    out = []
    for folder in Project.list_all():
        try:
            p = Project.open(paths.projects_dir() / folder)
        except Exception:
            continue
        out.append({"folder": folder, "name": p.data["name"], "aspect": p.data["aspect"], "preset": p.data["preset"],
                    "scenes": len(p.scenes), "duration": p.data.get("audio_duration") or 0,
                    "synced": bool(p.data.get("sync", {}).get("done")), "outputs": outputs(p),
                    "modified": (p.dir / "project.json").stat().st_mtime,
                    "thumb_scene": next((s["number"] for s in p.scenes if s.get("media")), None)})
    return out


@app.post("/api/projects")
def create_project(body: NewProject):
    name = body.name.strip()
    if not name:
        raise UserError("Type a project name.")
    p = Project.create(name, body.aspect if body.aspect in ("16:9", "9:16") else "16:9",
                       body.preset or presets.names()[0])
    return state(p)


@app.get("/api/projects/{folder}")
def get_project(folder: str):
    return state(load(folder))


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    settings: Optional[dict] = None
    aspect: Optional[str] = None
    render: Optional[dict] = None
    reset_settings: Optional[bool] = None


@app.patch("/api/projects/{folder}")
def patch_project(folder: str, body: ProjectPatch):
    p = load(folder)
    if body.name is not None and body.name.strip():
        p.data["name"] = body.name.strip()[:120]
    if body.reset_settings:
        st = presets.get(p.data["preset"])
        st["aspect"] = p.data["aspect"]
        p.data["settings"] = st
    if body.settings is not None:
        p.data["settings"] = presets.normalize(body.settings)
        p.data["settings"]["aspect"] = p.data["aspect"]
    if body.aspect in ("16:9", "9:16"):
        p.data["aspect"] = body.aspect
        p.data["settings"]["aspect"] = body.aspect
    if body.render is not None:
        p.data["render"] = {"resolution": body.render.get("resolution", "1080p"),
                            "quality": body.render.get("quality", "standard")}
    p.save()
    return state(p)


@app.delete("/api/projects/{folder}")
def delete_project(folder: str):
    p = load(folder)
    if _running_job() and _running_job()["project"] == folder:
        raise UserError("This project is busy - stop the render first.")
    shutil.rmtree(p.dir)
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ step 1
@app.post("/api/projects/{folder}/voice")
def upload_voice(folder: str, files: List[UploadFile] = File(...)):
    p = load(folder)
    tmp, saved = save_uploads(files)
    try:
        bad = [f.name for f in saved if f.suffix.lower() not in AUDIO_EXT]
        if bad:
            raise UserError(f"Not an audio file: {', '.join(bad)}. Use MP3, WAV or M4A.")
        pipeline.save_voice(p, saved)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return state(p)


@app.post("/api/script/read")
def read_script(file: UploadFile = File(...)):
    tmp, saved = save_uploads([file])
    try:
        if saved[0].suffix.lower() not in (".docx", ".txt", ".md"):
            raise UserError("Use a .docx, .txt or .md script file.")
        text = script_parser.read_script_file(saved[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    scenes, warnings = pipeline.check_script(text)
    return {"text": text, "count": len(scenes), "warnings": warnings}


class ScriptBody(BaseModel):
    text: str
    expected: Optional[int] = None
    confirm: bool = False
    save: bool = True


@app.post("/api/projects/{folder}/script")
def save_script(folder: str, body: ScriptBody):
    p = load(folder)
    scenes, warnings = pipeline.check_script(body.text, body.expected or None)
    if not scenes:
        raise UserError(warnings[0] if warnings else "No scenes found in the script.")
    mismatch = bool(body.expected) and len(scenes) != int(body.expected)
    if not body.save or (mismatch and not body.confirm):
        return {"saved": False, "needs_confirm": mismatch, "count": len(scenes), "warnings": warnings,
                "scenes": [{"number": s["number"], "text": s["text"]} for s in scenes]}
    if p.data.get("script_text") == body.text and p.scenes and p.data.get("expected_scenes") == body.expected:
        return {"saved": True, "unchanged": True, "count": len(scenes), "warnings": warnings, "project": state(p)}
    pipeline.save_script(p, body.text, body.expected or None)
    return {"saved": True, "count": len(scenes), "warnings": warnings, "project": state(p)}


class SyncBody(BaseModel):
    model: str = "small"
    language: str = "en"


@app.post("/api/projects/{folder}/sync")
def sync(folder: str, body: SyncBody):
    p = load(folder)
    if not p.data.get("voice_files"):
        raise UserError("Upload the voice-over audio first.")
    if not p.scenes:
        raise UserError("Add the script first.")
    model = body.model if body.model in MODEL_CHOICES else "small"

    def work(progress):
        pp = load(folder)
        res = pipeline.run_sync(pp, model, body.language, progress=progress)
        flagged = [s["number"] for s in res["scenes"] if s["flag"]]
        progress(1.0, f"Synced {len(res['scenes'])} scenes" + (f" - {len(flagged)} need checking" if flagged else ""))
        return {"match_rate": res["match_rate"], "flagged": flagged}

    return start_job("sync", folder, work)


# ------------------------------------------------------------------------------------------------ media
@app.post("/api/projects/{folder}/media")
def upload_media(folder: str, files: List[UploadFile] = File(...)):
    p = load(folder)
    if not p.scenes:
        raise UserError("Add the script first, so SceneForge knows the scenes.")
    tmp, saved = save_uploads(files)
    try:
        mapping, unmatched, notes, copied = pipeline.import_media(p, saved)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"added": len(copied), "unmatched": unmatched, "notes": notes, "project": state(p)}


class FolderBody(BaseModel):
    path: str


@app.post("/api/projects/{folder}/media/folder")
def media_from_folder(folder: str, body: FolderBody):
    p = load(folder)
    d = Path(body.path.strip().strip('"'))
    if not d.is_dir():
        raise UserError(f"Folder not found: {d}")
    mapping, unmatched, notes, copied = pipeline.import_media(p, [d])
    return {"added": len(copied), "unmatched": unmatched, "notes": notes, "project": state(p)}


@app.post("/api/projects/{folder}/scenes/{number}/media")
def swap_media(folder: str, number: int, file: UploadFile = File(...)):
    p = load(folder)
    if not p.scene(number):
        raise HTTPException(404, "scene not found")
    tmp, saved = save_uploads([file])
    try:
        pipeline.set_scene_media(p, number, saved[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return state(p)


@app.post("/api/projects/{folder}/audio/{kind}")
def upload_audio_extra(folder: str, kind: str, file: UploadFile = File(...)):
    if kind not in ("music", "sfx"):
        raise HTTPException(404)
    p = load(folder)
    tmp, saved = save_uploads([file])
    try:
        f = saved[0]
        if f.suffix.lower() not in AUDIO_EXT:
            raise UserError("Use an audio file (MP3, WAV, M4A ...).")
        dest = p.copy_in(f, p.audio_dir, new_name=f"{kind}{f.suffix.lower()}")
        p.data[kind] = p.rel(dest)
        p.save()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return state(p)


@app.delete("/api/projects/{folder}/audio/{kind}")
def remove_audio_extra(folder: str, kind: str):
    p = load(folder)
    if kind in ("music", "sfx"):
        p.data[kind] = None
        p.save()
    return state(p)


# ------------------------------------------------------------------------------------------------ review
class StartBody(BaseModel):
    delta: Optional[float] = None
    absolute: Optional[float] = None
    reset: bool = False


@app.post("/api/projects/{folder}/scenes/{number}/start")
def set_start(folder: str, number: int, body: StartBody):
    p = load(folder)
    if body.reset:
        pipeline.reset_start(p, number)
    else:
        pipeline.nudge(p, number, delta=body.delta, absolute=body.absolute)
    return state(p)


@app.get("/api/projects/{folder}/thumb/{number}")
def thumb(folder: str, number: int):
    p = load(folder)
    s = p.scene(number)
    t = thumbs.thumbnail(p, s.get("media")) if s else None
    if not t:
        raise HTTPException(404)
    return FileResponse(t, headers={"Cache-Control": "max-age=3600"})


@app.get("/api/projects/{folder}/file/{rel:path}")
def project_file(folder: str, rel: str):
    p = load(folder)
    f = (p.dir / rel).resolve()
    if p.dir.resolve() not in f.parents or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


@app.post("/api/projects/{folder}/preview/{number}")
def preview(folder: str, number: int):
    p = load(folder)
    if not p.data.get("sync", {}).get("done"):
        raise UserError("Sync the scenes first.")

    def work(progress):
        pp = load(folder)
        size = (640, 360) if pp.data["aspect"] != "9:16" else (360, 640)
        out = Renderer(pp, quality="fast", size=size, tag="preview", progress=progress).preview(number)
        return {"file": pp.rel(out), "v": int(time.time())}

    return start_job("preview", folder, work)


class RenderBody(BaseModel):
    resolution: str = "1080p"
    quality: str = "standard"


@app.post("/api/projects/{folder}/render")
def start_render(folder: str, body: RenderBody):
    p = load(folder)
    if not p.data.get("sync", {}).get("done"):
        raise UserError("Sync the scenes first (step 1).")
    problems = p.timeline_problems()
    if problems:
        raise UserError(" ".join(problems))
    p.data["render"] = {"resolution": body.resolution if body.resolution in ("1080p", "4K") else "1080p",
                        "quality": body.quality if body.quality in render.QUALITY else "standard"}
    p.save()

    def work(progress):
        pp = load(folder)
        t = time.time()
        out = Renderer(pp, progress=progress).run()
        return {"file": pp.rel(out), "seconds": round(time.time() - t, 1), "v": int(time.time())}

    return start_job("render", folder, work)


@app.post("/api/projects/{folder}/open-output")
def open_output(folder: str):
    p = load(folder)
    target = str(p.output_dir)
    try:
        if paths.IS_WINDOWS:
            os.startfile(target)  # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return {"path": target}


@app.post("/api/projects/{folder}/clean")
def clean(folder: str):
    p = load(folder)
    for d in p.work_dir.iterdir():
        if d.is_dir() and (d.name.startswith(("render_", "clips_")) or d.name == "thumbs"):
            shutil.rmtree(d, ignore_errors=True)
    for f in p.work_dir.glob("preview_scene_*.mp4"):
        f.unlink(missing_ok=True)
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ presets etc.
@app.get("/api/presets")
def get_presets():
    return presets.load_all()


@app.put("/api/presets/{name}")
def put_preset(name: str, body: dict):
    presets.save(name, body)
    return presets.load_all()


class NameBody(BaseModel):
    new_name: str


@app.post("/api/presets/{name}/duplicate")
def dup_preset(name: str, body: NameBody):
    presets.duplicate(name, body.new_name.strip())
    return presets.load_all()


@app.post("/api/presets/{name}/rename")
def ren_preset(name: str, body: NameBody):
    presets.rename(name, body.new_name.strip())
    return presets.load_all()


@app.delete("/api/presets/{name}")
def del_preset(name: str):
    presets.delete(name)
    return presets.load_all()


@app.post("/api/presets-reset")
def reset_presets():
    presets.reset_defaults()
    return presets.load_all()


@app.get("/api/meta")
def meta():
    from . import __version__
    return {"version": __version__, "fonts": list(fonts.list_fonts().keys()), "models": MODEL_CHOICES[:2],
            "projects_dir": str(paths.projects_dir()), "motion_types": presets.MOTION_TYPES,
            "transition_types": presets.TRANSITION_TYPES, "fit_modes": presets.CLIP_FIT_MODES}


SAMPLE_SCRIPT = """My Video Title (this line is ignored)

Scene 1: The ancient city was buried under the sand for two thousand years.

Scene 2: In 1922, explorers finally found the hidden entrance. [image: torch-lit tunnel]

Scene 3: Inside, they discovered walls covered with strange golden symbols.
"""


@app.get("/api/sample-script")
def sample_script():
    return PlainTextResponse(SAMPLE_SCRIPT, headers={"Content-Disposition": 'attachment; filename="sample_script.txt"'})


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
