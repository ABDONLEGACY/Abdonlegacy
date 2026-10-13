"""SceneForge - personal scene-synced video editor. Runs only on this computer (http://127.0.0.1:7860)."""
import copy
import html
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path

# Nothing leaves this computer: switch off Gradio / Hugging Face usage statistics before importing them.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import gradio as gr  # noqa: E402

from sceneforge import fonts, pipeline, presets, render, script_parser, thumbs  # noqa: E402
from sceneforge.media import media_kind  # noqa: E402
from sceneforge.project import Project  # noqa: E402
from sceneforge.render import Renderer, fmt_time  # noqa: E402
from sceneforge.transcribe import MODEL_CHOICES  # noqa: E402

APP_TITLE = "SceneForge"
LANGUAGES = [("English", "en"), ("Detect automatically", "auto"), ("French", "fr"), ("Spanish", "es"),
             ("German", "de"), ("Portuguese", "pt"), ("Italian", "it"), ("Dutch", "nl"), ("Arabic", "ar"),
             ("Hindi", "hi")]
FIT_LABELS = [("Slow down a little, then freeze the last frame", "slow_then_freeze"),
              ("Slow down a little, then loop the last part", "slow_then_loop"),
              ("Freeze the last frame", "freeze"), ("Loop the last part", "loop")]
MOTION_LABELS = [("Zoom in", "zoom_in"), ("Zoom out", "zoom_out"), ("Pan left", "pan_left"),
                 ("Pan right", "pan_right"), ("Zoom in + pan", "zoom_in_pan"), ("Zoom out + pan", "zoom_out_pan")]
EASING_LABELS = [("Smooth start & stop", "ease_in_out"), ("Gentle (sine)", "ease_in_out_sine"),
                 ("Steady (linear)", "linear"), ("Fast start, slow end", "ease_out")]
TRANS_LABELS = [("Fade (cross-dissolve)", "fade"), ("Slide left", "slide_left"), ("Slide right", "slide_right"),
                ("Zoom in", "zoom_in"), ("Zoom out", "zoom_out")]
TRANS_MODE_LABELS = [("Rotate between the ticked types", "rotate"), ("Always use one type", "lock"),
                     ("Hard cut (no transition)", "cut")]
CAPTION_MODE_LABELS = [("Word-by-word highlight", "word"), ("Short phrases", "phrase"), ("One word at a time", "single")]


# ---------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------
def need_project(folder):
    if not folder:
        raise gr.Error("Open or create a project first (step 1).")
    try:
        return Project.open(folder)
    except FileNotFoundError:
        raise gr.Error("That project folder no longer exists. Open another project in step 1.")


def friendly(fn):
    """Show any unexpected error as a readable pop-up instead of a crash."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except gr.Error:
            raise
        except render.Stopped:
            raise gr.Error("Rendering stopped. Press Render again to continue where it left off.")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            raise gr.Error(str(e)[:1500] or e.__class__.__name__)
    wrapper.__name__ = fn.__name__
    return wrapper


def tstr(sec):
    if sec is None:
        return "-"
    sec = float(sec)
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:05.2f}"


def header_md(p):
    if p is None:
        return "### No project open - start with step 1"
    d = p.data
    dur = f" - voiceover {fmt_time(d['audio_duration'])}" if d.get("audio_duration") else ""
    return f"### Project: **{html.escape(d['name'])}** ({d['aspect']}, preset *{d['preset']}*){dur}  \n`{p.dir}`"


def file_paths(files):
    if not files:
        return []
    if not isinstance(files, list):
        files = [files]
    out = []
    for f in files:
        out.append(f if isinstance(f, str) else getattr(f, "name", None) or f.get("path"))
    return [x for x in out if x]


def open_folder(path):
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------
# settings form (used for presets and for the project's own settings)
# ---------------------------------------------------------------------------------------------------------
FIELDS = [  # (section, key)
    ("", "aspect"),
    ("motion", "zoom_min"), ("motion", "zoom_max"), ("motion", "pan_min"), ("motion", "pan_max"),
    ("motion", "types"), ("motion", "easing"),
    ("transitions", "mode"), ("transitions", "types"), ("transitions", "lock_type"), ("transitions", "duration"),
    ("clips", "fit_mode"), ("clips", "max_slowdown"), ("clips", "keep_audio"), ("clips", "clip_volume"),
    ("captions", "enabled"), ("captions", "mode"), ("captions", "font"), ("captions", "size"),
    ("captions", "color"), ("captions", "highlight_color"), ("captions", "outline_color"), ("captions", "outline"),
    ("captions", "shadow"), ("captions", "position"), ("captions", "max_words"), ("captions", "uppercase"),
    ("captions", "pop"),
    ("audio", "music_volume"), ("audio", "duck"), ("audio", "sfx_volume"),
    ("sync", "lead_in"),
]


def build_settings_form():
    font_names = list(fonts.list_fonts().keys()) or ["Arial Bold"]
    c = {}
    c["aspect"] = gr.Radio([("16:9 landscape", "16:9"), ("9:16 portrait", "9:16")], label="Aspect ratio")
    with gr.Accordion("Image motion (keyframes)", open=False):
        with gr.Row():
            c["zoom_min"] = gr.Slider(1.0, 1.5, step=0.01, label="Smallest zoom (1.05 = 5 %)")
            c["zoom_max"] = gr.Slider(1.0, 1.5, step=0.01, label="Largest zoom")
        with gr.Row():
            c["pan_min"] = gr.Slider(0.0, 0.3, step=0.01, label="Shortest pan (fraction of the width)")
            c["pan_max"] = gr.Slider(0.0, 0.3, step=0.01, label="Longest pan")
        c["mtypes"] = gr.CheckboxGroup(MOTION_LABELS, label="Movements to use (never the same twice in a row)")
        c["easing"] = gr.CheckboxGroup(EASING_LABELS, label="Speed curves to pick from")
    with gr.Accordion("Transitions", open=False):
        c["tmode"] = gr.Radio(TRANS_MODE_LABELS, label="Transition style")
        c["ttypes"] = gr.CheckboxGroup(TRANS_LABELS, label="Types to rotate between")
        with gr.Row():
            c["lock_type"] = gr.Dropdown(TRANS_LABELS, label="The one type (when 'Always use one type')")
            c["tdur"] = gr.Slider(0.1, 2.0, step=0.05, label="Transition length (seconds)")
    with gr.Accordion("Video clips", open=False):
        c["fit_mode"] = gr.Dropdown(FIT_LABELS, label="When a clip is shorter than its scene")
        c["max_slowdown"] = gr.Slider(0.0, 0.5, step=0.01, label="Maximum slow-down (0.20 = 20 %)")
        with gr.Row():
            c["keep_audio"] = gr.Checkbox(label="Keep clip audio (sound effects under the voice)")
            c["clip_volume"] = gr.Slider(0.0, 1.0, step=0.01, label="Clip audio volume (0.25 = 25 %)")
    with gr.Accordion("Captions", open=False):
        with gr.Row():
            c["cap_on"] = gr.Checkbox(label="Show captions")
            c["cap_mode"] = gr.Radio(CAPTION_MODE_LABELS, label="Caption style")
        with gr.Row():
            c["font"] = gr.Dropdown(font_names, label="Font", allow_custom_value=True, filterable=True)
            c["size"] = gr.Slider(20, 160, step=1, label="Size (pixels at 1080p)")
            c["max_words"] = gr.Slider(2, 8, step=1, label="Most words per caption")
        with gr.Row():
            c["color"] = gr.ColorPicker(label="Text colour")
            c["hl"] = gr.ColorPicker(label="Highlight colour")
            c["oc"] = gr.ColorPicker(label="Outline colour")
            c["outline"] = gr.Slider(0, 15, step=1, label="Outline thickness")
        with gr.Row():
            c["position"] = gr.Radio([("Bottom", "bottom"), ("Middle", "middle"), ("Top", "top")], label="Position")
            c["shadow"] = gr.Checkbox(label="Soft shadow")
            c["uppercase"] = gr.Checkbox(label="CAPITAL LETTERS")
            c["pop"] = gr.Checkbox(label="Pop animation")
    with gr.Accordion("Audio & sync", open=False):
        with gr.Row():
            c["music_volume"] = gr.Slider(0.0, 1.0, step=0.01, label="Music volume")
            c["duck"] = gr.Checkbox(label="Lower music while the voice speaks (ducking)")
            c["sfx_volume"] = gr.Slider(0.0, 1.0, step=0.01, label="Transition sound volume")
        c["lead_in"] = gr.Slider(0.0, 0.5, step=0.01,
                                 label="Cut this many seconds BEFORE each scene's first word (0 = exactly on the word)")
    order = ["aspect", "zoom_min", "zoom_max", "pan_min", "pan_max", "mtypes", "easing", "tmode", "ttypes",
             "lock_type", "tdur", "fit_mode", "max_slowdown", "keep_audio", "clip_volume", "cap_on", "cap_mode",
             "font", "size", "color", "hl", "oc", "outline", "shadow", "position", "max_words", "uppercase", "pop",
             "music_volume", "duck", "sfx_volume", "lead_in"]
    return [c[k] for k in order]


def settings_to_values(st):
    st = presets.normalize(st)
    out = []
    for sec, key in FIELDS:
        out.append(st[key] if not sec else st[sec][key])
    return out


def _color(v, default):
    rgb = __import__("sceneforge.captions", fromlist=["hex_to_rgb"]).hex_to_rgb(v or default)
    return "#%02X%02X%02X" % rgb


def values_to_settings(base, values):
    st = copy.deepcopy(presets.normalize(base))
    for (sec, key), v in zip(FIELDS, values):
        if key in ("color", "highlight_color", "outline_color"):
            v = _color(v, "#FFFFFF")
        if key in ("size", "outline", "max_words") and v is not None:
            v = int(v)
        if sec:
            st[sec][key] = v
        else:
            st[key] = v
    m = st["motion"]
    m["zoom_min"], m["zoom_max"] = sorted((m["zoom_min"], m["zoom_max"]))
    m["pan_min"], m["pan_max"] = sorted((m["pan_min"], m["pan_max"]))
    if not m["types"]:
        raise gr.Error("Tick at least one image movement.")
    if not m["easing"]:
        m["easing"] = ["ease_in_out"]
    if st["transitions"]["mode"] == "rotate" and not st["transitions"]["types"]:
        raise gr.Error("Tick at least one transition type, or choose 'Hard cut'.")
    return st


# ---------------------------------------------------------------------------------------------------------
# step 1 - project
# ---------------------------------------------------------------------------------------------------------
@friendly
def create_project(name, aspect, preset_name):
    name = (name or "").strip()
    if not name:
        raise gr.Error("Type a project name.")
    p = Project.create(name, aspect or "16:9", preset_name or presets.names()[0])
    gr.Info(f"Project '{name}' created.")
    return (str(p.dir), header_md(p), gr.Dropdown(choices=Project.list_all(), value=p.dir.name),
            gr.Tabs(selected="voice"))


@friendly
def open_project(name):
    if not name:
        raise gr.Error("Pick a project from the list.")
    from sceneforge import paths
    p = Project.open(paths.projects_dir() / name)
    return str(p.dir), header_md(p), gr.Tabs(selected="voice")


def refresh_projects():
    return gr.Dropdown(choices=Project.list_all())


# ---------------------------------------------------------------------------------------------------------
# step 2 - script & voice
# ---------------------------------------------------------------------------------------------------------
def voice_status(p):
    if not p or not p.data.get("voice_files"):
        return "No voiceover saved yet."
    names = [Path(v).name for v in p.data["voice_files"]]
    lines = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
    return f"**Voiceover saved** - {len(names)} file(s), total **{fmt_time(p.data['audio_duration'])}** " \
           f"({p.data['audio_duration']:.2f} s). Joined in this order:\n\n{lines}"


def load_step2(folder):
    if not folder:
        return "No project open.", "", None, None
    p = Project.open(folder)
    return voice_status(p), p.data.get("script_text", ""), p.data.get("expected_scenes"), scenes_df(p, brief=True)


@friendly
def save_voice(folder, files, progress=gr.Progress()):
    p = need_project(folder)
    paths_ = file_paths(files)
    if not paths_:
        raise gr.Error("Choose your voiceover file(s) first.")
    progress(0.2, desc="Joining voiceover ...")
    dur = pipeline.save_voice(p, paths_)
    if dur > 40 * 60:
        gr.Warning(f"The voiceover is {fmt_time(dur)} long - SceneForge is tested up to 30 minutes.")
    return voice_status(p), header_md(p)


@friendly
def load_script_file(file):
    paths_ = file_paths(file)
    if not paths_:
        return gr.update()
    return script_parser.read_script_file(paths_[0])


def scenes_df(p_or_scenes, brief=False):
    scenes = p_or_scenes.scenes if isinstance(p_or_scenes, Project) else p_or_scenes
    rows = []
    for s in scenes or []:
        words = s["text"].split()
        rows.append([s["number"], " ".join(words[:10]) + (" ..." if len(words) > 10 else ""), len(words)])
    return rows


@friendly
def check_script(text, expected):
    scenes, warnings = pipeline.check_script(text, expected or None)
    msg = f"**{len(scenes)} scenes found.**"
    if warnings:
        msg += "\n\n" + "\n".join(f"- {w}" for w in warnings)
    return msg, scenes_df(scenes)


@friendly
def save_script(folder, text, expected, confirmed):
    p = need_project(folder)
    scenes, warnings = pipeline.check_script(text, expected or None)
    if not scenes:
        raise gr.Error(warnings[0] if warnings else "No scenes found.")
    mismatch = expected and len(scenes) != int(expected)
    if mismatch and not confirmed:
        msg = (f"**Please check:** you expected {int(expected)} scenes but the script has {len(scenes)}. "
               "Fix the script, or tick 'Continue anyway' and press Save again.")
        return msg + "\n\n" + "\n".join(f"- {w}" for w in warnings), scenes_df(scenes), gr.Tabs()
    scenes, warnings = pipeline.save_script(p, text, expected or None)
    if not p.data.get("voice_files"):
        gr.Warning("Script saved. Don't forget to save the voiceover too.")
        nxt = gr.Tabs()
    else:
        gr.Info(f"Script saved: {len(scenes)} scenes.")
        nxt = gr.Tabs(selected="sync")
    msg = f"**Saved {len(scenes)} scenes.**" + ("\n\n" + "\n".join(f"- {w}" for w in warnings) if warnings else "")
    return msg, scenes_df(scenes), nxt


# ---------------------------------------------------------------------------------------------------------
# step 3 - sync
# ---------------------------------------------------------------------------------------------------------
def sync_table(p):
    rows = []
    tl = {r["number"]: r for r in p.timeline()} if p.data.get("sync", {}).get("done") else {}
    for s in p.scenes:
        words = s["text"].split()
        r = tl.get(s["number"])
        rows.append([s["number"], tstr(r["start"]) if r else "-", tstr(r["duration"]) if r else "-",
                     " ".join(words[:8]), ("%d%%" % round(100 * s["confidence"])) if s.get("confidence") is not None else "-",
                     ("⚠ " + s["flag"]) if s.get("flag") else ("OK" if r else "not synced yet")])
    return rows


def sync_summary(p):
    sy = p.data.get("sync", {})
    if not sy.get("done"):
        return "Not synced yet. Press **Find scene starts**."
    flagged = [s["number"] for s in p.scenes if s.get("flag")]
    msg = (f"**Synced with the '{sy.get('model')}' model.** {round(100 * sy.get('match_rate', 0))}% of script words "
           f"were found in the voiceover.")
    if sy.get("match_rate", 1) < 0.5:
        msg += "\n\n⚠ **Less than half the script matched the voice** - is this the right script for this voiceover?"
    if flagged:
        msg += (f"\n\n⚠ **{len(flagged)} scene(s) need checking:** {flagged[:40]}. Their start was estimated - check "
                "them in step 5 (you can nudge them there).")
    else:
        msg += "\n\nAll scenes were found confidently."
    return msg


def load_step3(folder):
    if not folder:
        return "No project open.", None
    p = Project.open(folder)
    return sync_summary(p), sync_table(p)


@friendly
def run_sync(folder, model, language, progress=gr.Progress()):
    p = need_project(folder)
    if not p.data.get("voice_files"):
        raise gr.Error("Save the voiceover first (step 2).")
    if not p.scenes:
        raise gr.Error("Save the script first (step 2).")
    edited = [s["number"] for s in p.scenes if s.get("edited")]

    def cb(frac, msg):
        progress(frac, desc=msg)

    pipeline.run_sync(p, model, language, progress=cb)
    if edited:
        gr.Warning(f"Scene starts you had nudged were reset by the new sync: {edited[:20]}")
    return sync_summary(p), sync_table(p), gr.Tabs(selected="media")


# ---------------------------------------------------------------------------------------------------------
# step 4 - media
# ---------------------------------------------------------------------------------------------------------
def media_table(p):
    rows = []
    for s in p.scenes:
        f = p.path(s.get("media"))
        ok = f is not None and f.exists()
        rows.append([s["number"], f.name if ok else "", media_kind(f) if ok else "",
                     "OK" if ok else "❌ MISSING"])
    return rows


def media_summary(p, extra=""):
    if not p.scenes:
        return "Save the script first (step 2)."
    missing = pipeline.missing_media(p)
    msg = (f"**{len(p.scenes) - len(missing)} of {len(p.scenes)} scenes have media.**")
    if missing:
        msg += f"\n\n❌ **Missing media for scenes:** {missing[:60]}{' ...' if len(missing) > 60 else ''}"
    music = p.path(p.data.get("music"))
    sfx = p.path(p.data.get("sfx"))
    msg += f"\n\nBackground music: **{music.name if music else 'none'}** - Transition sound: **{sfx.name if sfx else 'none'}**"
    return msg + (("\n\n" + extra) if extra else "")


def load_step4(folder):
    if not folder:
        return "No project open.", None
    p = Project.open(folder)
    return media_summary(p), media_table(p)


@friendly
def add_media(folder, files, folder_files, path_text, progress=gr.Progress()):
    p = need_project(folder)
    if not p.scenes:
        raise gr.Error("Save the script first (step 2), so SceneForge knows the scenes.")
    sources = file_paths(files) + file_paths(folder_files)
    if path_text and path_text.strip():
        d = Path(path_text.strip().strip('"'))
        if not d.exists():
            raise gr.Error(f"Folder not found: {d}")
        sources.append(str(d))
    if not sources:
        raise gr.Error("Choose files or a folder first.")
    progress(0.3, desc="Copying media into the project ...")
    mapping, unmatched, notes, copied = pipeline.import_media(p, sources)
    extra = f"Added {len(copied)} file(s)."
    if unmatched:
        extra += f"\n\nThese files have no scene number in their name and were not used: {unmatched[:20]}"
    if notes:
        extra += "\n\n" + "\n".join(f"- {n}" for n in notes)
    return media_summary(p, extra), media_table(p), None, None


@friendly
def set_audio_extra(folder, kind, file):
    p = need_project(folder)
    paths_ = file_paths(file)
    if not paths_:
        raise gr.Error("Choose a file first.")
    f = Path(paths_[0])
    dest = p.copy_in(f, p.audio_dir, new_name=f"{kind}{f.suffix.lower()}")
    p.data[kind] = p.rel(dest)
    p.save()
    return media_summary(p), None


@friendly
def clear_audio_extra(folder, kind):
    p = need_project(folder)
    p.data[kind] = None
    p.save()
    return media_summary(p)


# ---------------------------------------------------------------------------------------------------------
# step 5 - review & export
# ---------------------------------------------------------------------------------------------------------
def review_html(p):
    if not p.scenes:
        return "<p>No scenes yet.</p>"
    tl = {r["number"]: r for r in p.timeline()}
    rows = []
    for s in p.scenes:
        r = tl[s["number"]]
        th = thumbs.thumbnail(p, s.get("media"))
        img = (f'<img src="{thumbs.data_uri(th)}" width="128" height="72">' if th
               else '<div class="sf-missing">no media</div>')
        words = html.escape(" ".join(s["text"].split()[:12]))
        flag = s.get("flag") or ""
        if s.get("edited"):
            flag = (flag + " " if flag else "") + "(start moved by you)"
        warn = f'<span class="sf-flag">⚠ {html.escape(flag)}</span>' if s.get("flag") else html.escape(flag)
        kind = media_kind(p.path(s.get("media"))) if s.get("media") else ""
        rows.append(f"<tr class='{'sf-flagged' if s.get('flag') else ''}'><td><b>{s['number']}</b></td>"
                    f"<td>{tstr(r['start'])}</td><td>{tstr(r['end'])}</td><td>{r['duration']:.2f}s</td>"
                    f"<td>{img}<br><small>{kind}</small></td><td>{words}</td><td>{warn}</td></tr>")
    return ("<div class='sf-table'><table><thead><tr><th>Scene</th><th>Start</th><th>End</th><th>Length</th>"
            "<th>Media</th><th>First words</th><th>Warning</th></tr></thead><tbody>" + "".join(rows) +
            "</tbody></table></div>")


def scene_choices(p):
    return [(f"Scene {s['number']}" + (" ⚠" if s.get("flag") else ""), s["number"]) for s in p.scenes]


def scene_detail(p, number):
    s = p.scene(number) if number is not None else None
    if not s:
        return "Pick a scene.", None
    r = next(x for x in p.timeline() if x["number"] == number)
    auto = s.get("auto_start")
    msg = (f"**Scene {number}** starts at **{tstr(r['start'])}**, ends {tstr(r['end'])} ({r['duration']:.2f} s).  \n"
           f"Detected start: {tstr(auto)}  \nMedia: {Path(s['media']).name if s.get('media') else '❌ missing'}  \n"
           f"Narration: _{html.escape(s['text'][:300])}_")
    if s.get("flag"):
        msg += f"\n\n⚠ **{s['flag']}**"
    return msg, r["start"]


def load_step5(folder):
    if not folder:
        return "No project open.", gr.Dropdown(choices=[]), "", None, *settings_to_values(presets.BASE), \
            "1080p", "standard", ""
    p = Project.open(folder)
    choices = scene_choices(p)
    first = next((s["number"] for s in p.scenes if s.get("flag")), p.scenes[0]["number"] if p.scenes else None)
    detail, start = scene_detail(p, first) if first is not None else ("", None)
    rs = p.data.get("render", {})
    return (review_html(p), gr.Dropdown(choices=choices, value=first), detail, start,
            *settings_to_values(p.settings), rs.get("resolution", "1080p"), rs.get("quality", "standard"),
            check_ready(p))


def check_ready(p):
    problems = []
    if not p.data.get("voice_files"):
        problems.append("no voiceover (step 2)")
    if not p.scenes:
        problems.append("no script (step 2)")
    elif not p.data.get("sync", {}).get("done"):
        problems.append("scenes not synced yet (step 3)")
    missing = pipeline.missing_media(p) if p.scenes else []
    msg = ""
    if problems:
        msg = "❌ Not ready: " + "; ".join(problems)
    elif missing:
        msg = f"⚠ Scenes without media will show a dark 'media missing' card: {missing[:30]}"
    flagged = [s["number"] for s in p.scenes if s.get("flag")]
    if flagged and not problems:
        msg += ("\n\n" if msg else "") + f"⚠ Flagged scenes to check before rendering: {flagged[:30]}"
    if not msg:
        msg = "✅ Ready to render."
    out = p.output_dir
    vids = sorted(out.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if out.exists() else []
    vids = [v for v in vids if ".part" not in v.name]
    if vids:
        msg += f"\n\nLast video: `{vids[0]}`"
    return msg


@friendly
def pick_scene(folder, number):
    p = need_project(folder)
    return scene_detail(p, number)


@friendly
def nudge_scene(folder, number, delta):
    p = need_project(folder)
    if number is None:
        raise gr.Error("Pick a scene first.")
    pipeline.nudge(p, number, delta=delta)
    detail, start = scene_detail(p, number)
    return review_html(p), detail, start, check_ready(p)


@friendly
def set_scene_start(folder, number, value):
    p = need_project(folder)
    if number is None or value is None:
        raise gr.Error("Pick a scene and type a start time in seconds.")
    pipeline.nudge(p, number, absolute=value)
    detail, start = scene_detail(p, number)
    return review_html(p), detail, start, check_ready(p)


@friendly
def reset_scene_start(folder, number):
    p = need_project(folder)
    pipeline.reset_start(p, number)
    detail, start = scene_detail(p, number)
    return review_html(p), detail, start, check_ready(p)


@friendly
def swap_media(folder, number, file):
    p = need_project(folder)
    paths_ = file_paths(file)
    if number is None or not paths_:
        raise gr.Error("Pick a scene and choose the new image or clip.")
    pipeline.set_scene_media(p, number, paths_[0])
    detail, start = scene_detail(p, number)
    return review_html(p), detail, None, check_ready(p)


def preview_size(p):
    return (640, 360) if p.data["aspect"] != "9:16" else (360, 640)


@friendly
def preview_scene(folder, number, progress=gr.Progress()):
    p = need_project(folder)
    if number is None:
        raise gr.Error("Pick a scene first.")
    if not p.data.get("sync", {}).get("done"):
        raise gr.Error("Sync the scenes first (step 3).")
    r = Renderer(p, quality="fast", size=preview_size(p), tag="preview",
                 progress=lambda f, m: progress(f, desc=m))
    return str(r.preview(number))


@friendly
def save_project_settings(folder, *values):
    p = need_project(folder)
    p.data["settings"] = values_to_settings(p.settings, values)
    p.data["aspect"] = p.data["settings"]["aspect"]
    p.save()
    gr.Info("Project settings saved.")
    return review_html(p), header_md(p)


@friendly
def reset_project_settings(folder):
    p = need_project(folder)
    st = presets.get(p.data["preset"])
    st["aspect"] = p.data["aspect"]
    p.data["settings"] = st
    p.save()
    gr.Info(f"Settings reset to the '{p.data['preset']}' preset.")
    return settings_to_values(st)


@friendly
def do_render(folder, resolution, quality, progress=gr.Progress()):
    p = need_project(folder)
    if not p.data.get("sync", {}).get("done"):
        raise gr.Error("Sync the scenes first (step 3).")
    p.data["render"] = {"resolution": resolution, "quality": quality}
    p.save()
    problems = p.timeline_problems()
    if problems:
        raise gr.Error(" ".join(problems))
    r = Renderer(p, resolution=resolution, quality=quality, progress=lambda f, m: progress(f, desc=m))
    out = r.run()
    gr.Info(f"Video saved: {out}")
    return str(out), f"✅ **Finished!** Your video is saved here:\n\n`{out}`"


def stop_render():
    render.STOP.set()
    return "Stopping after the current frame ... (press Render again later to continue where it stopped)"


@friendly
def open_output(folder):
    p = need_project(folder)
    open_folder(p.output_dir)


@friendly
def clean_temp(folder):
    p = need_project(folder)
    import shutil
    n = 0
    for d in p.work_dir.iterdir():
        if d.is_dir() and (d.name.startswith("render_") or d.name.startswith("clips_") or d.name == "thumbs"):
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    for f in p.work_dir.glob("preview_scene_*.mp4"):
        f.unlink(missing_ok=True)
    gr.Info("Temporary render files deleted. The next render starts from the beginning.")


# ---------------------------------------------------------------------------------------------------------
# presets tab
# ---------------------------------------------------------------------------------------------------------
def preset_load(name):
    return settings_to_values(presets.get(name))


@friendly
def preset_save(name, *values):
    if not name:
        raise gr.Error("Pick a preset.")
    presets.save(name, values_to_settings(presets.get(name), values))
    gr.Info(f"Preset '{name}' saved.")


@friendly
def preset_duplicate(name, new_name):
    new_name = (new_name or "").strip()
    if not new_name:
        raise gr.Error("Type a name for the copy.")
    presets.duplicate(name, new_name)
    gr.Info(f"Created preset '{new_name}'.")
    return gr.Dropdown(choices=presets.names(), value=new_name), gr.Dropdown(choices=presets.names()), ""


@friendly
def preset_rename(name, new_name):
    new_name = (new_name or "").strip()
    if not new_name:
        raise gr.Error("Type the new name.")
    presets.rename(name, new_name)
    gr.Info(f"Renamed to '{new_name}'.")
    return gr.Dropdown(choices=presets.names(), value=new_name), gr.Dropdown(choices=presets.names()), ""


@friendly
def preset_delete(name):
    presets.delete(name)
    first = presets.names()[0]
    return gr.Dropdown(choices=presets.names(), value=first), gr.Dropdown(choices=presets.names(), value=first)


@friendly
def preset_reset():
    presets.reset_defaults()
    gr.Info("The three original presets were restored (your own extra presets were kept).")
    first = presets.names()[0]
    return gr.Dropdown(choices=presets.names(), value=first), gr.Dropdown(choices=presets.names(), value=first)


# ---------------------------------------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------------------------------------
CSS = """
.sf-table {max-height: 640px; overflow-y: auto; border: 1px solid var(--border-color-primary); border-radius: 8px;}
.sf-table table {width: 100%; border-collapse: collapse; font-size: 14px;}
.sf-table th {position: sticky; top: 0; background: var(--background-fill-secondary); z-index: 1;}
.sf-table td, .sf-table th {padding: 6px 8px; border-bottom: 1px solid var(--border-color-primary); text-align: left; vertical-align: middle;}
.sf-table tr.sf-flagged {background: rgba(255, 170, 0, 0.12);}
.sf-flag {color: #d97706; font-weight: 600;}
.sf-missing {width: 128px; height: 72px; display: flex; align-items: center; justify-content: center; background: #4442; color: #c33; font-size: 12px; border-radius: 4px;}
footer {display: none !important;}
"""


def build_ui():
    preset_names = presets.names()
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as demo:
        proj = gr.State("")
        gr.Markdown("# 🎬 SceneForge\nYour personal scene-synced video editor. Everything runs on this computer.")
        header = gr.Markdown(header_md(None))
        with gr.Tabs(selected="project") as tabs:
            # ---------------- step 1
            with gr.Tab("1. Project", id="project"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### New project")
                        new_name = gr.Textbox(label="Project name", elem_id="new-name", placeholder="e.g. Lost City of Atlantis")
                        new_aspect = gr.Radio([("16:9 landscape (YouTube)", "16:9"), ("9:16 portrait (Shorts)", "9:16")],
                                              value="16:9", label="Aspect ratio")
                        new_preset = gr.Dropdown(preset_names, value=preset_names[0], label="Style preset (your channel)")
                        create_btn = gr.Button("Create project", variant="primary")
                    with gr.Column():
                        gr.Markdown("### Open an existing project")
                        proj_list = gr.Dropdown(Project.list_all(), label="Your projects (newest first)")
                        with gr.Row():
                            open_btn = gr.Button("Open project", variant="primary")
                            refresh_btn = gr.Button("Refresh list")
                        from sceneforge import paths as _paths
                        gr.Markdown(f"Projects are saved in: `{_paths.projects_dir()}`")
            # ---------------- step 2
            with gr.Tab("2. Script & Voice", id="voice") as tab2:
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Voiceover\nOne file, or several files that will be joined in name order "
                                    "(e.g. part1, part2, part3). MP3, WAV or M4A.")
                        voice_files = gr.File(file_count="multiple", file_types=[".mp3", ".wav", ".m4a"],
                                              label="Voiceover file(s)", elem_id="voice-files")
                        voice_btn = gr.Button("Save voiceover", variant="primary")
                        voice_info = gr.Markdown(elem_id="voice-info")
                    with gr.Column():
                        gr.Markdown('### Script\nUpload a .docx, .txt or .md file, or paste the script below. '
                                    'Each scene starts with **"Scene 1:"**, **"Scene 2:"** ... '
                                    'Text in [square brackets] is treated as a note and not spoken.')
                        script_file = gr.File(file_types=[".docx", ".txt", ".md"], label="Script file", elem_id="script-file")
                        script_text = gr.Textbox(lines=14, max_lines=30, label="Script text")
                        with gr.Row():
                            expected = gr.Number(label="Expected number of scenes", precision=0, elem_id="expected")
                            confirm = gr.Checkbox(label="Continue anyway if the count doesn't match")
                        with gr.Row():
                            check_btn = gr.Button("Check script")
                            script_btn = gr.Button("Save script & continue", variant="primary")
                script_info = gr.Markdown(elem_id="script-info")
                script_df = gr.Dataframe(headers=["Scene", "First words", "Words"], interactive=False, max_height=400,
                                         label="Scenes found")
            # ---------------- step 3
            with gr.Tab("3. Scene Sync", id="sync") as tab3:
                gr.Markdown("SceneForge listens to the voiceover (speech recognition on this computer), then lines up "
                            "the whole script with it to find the exact moment each scene's first word is spoken. "
                            "The first time, the speech model is loaded (or downloaded once if it is missing). "
                            "A 30-minute voiceover takes roughly 10-20 minutes with the 'small' model.")
                with gr.Row():
                    model = gr.Radio(MODEL_CHOICES[:2], value="small",
                                     label="Speech model ('medium' is more accurate but about 3x slower)")
                    language = gr.Dropdown(LANGUAGES, value="en", label="Language of the voiceover")
                sync_btn = gr.Button("Find scene starts", variant="primary")
                sync_info = gr.Markdown(elem_id="sync-info")
                sync_df = gr.Dataframe(headers=["Scene", "Start", "Length", "First words", "Confidence", "Status"],
                                       interactive=False, max_height=500)
            # ---------------- step 4
            with gr.Tab("4. Media", id="media") as tab4:
                gr.Markdown('One image or video clip per scene. The **number in the file name** decides the scene: '
                            '"Scene 1.png", "scene_1.mp4" and "1.jpg" all go to scene 1. PNG, JPG, WEBP, MP4, MOV.')
                with gr.Row():
                    media_files = gr.File(file_count="multiple", label="Select many files at once", elem_id="media-files")
                    media_folder = gr.File(file_count="directory", label="...or pick a whole folder")
                media_path = gr.Textbox(label="...or type/paste a folder path on this computer (fastest for big clips)",
                                        placeholder=r"C:\Users\me\Videos\My Video\media")
                media_btn = gr.Button("Add media", variant="primary")
                media_info = gr.Markdown(elem_id="media-info")
                with gr.Row():
                    with gr.Column():
                        music_file = gr.File(label="Background music (optional, looped and ducked under the voice)", elem_id="music-file",
                                             file_types=[".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"])
                        with gr.Row():
                            music_btn = gr.Button("Use this music")
                            music_clear = gr.Button("Remove music")
                    with gr.Column():
                        sfx_file = gr.File(label="Transition sound, e.g. a whoosh (optional)", elem_id="sfx-file",
                                           file_types=[".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"])
                        with gr.Row():
                            sfx_btn = gr.Button("Use this sound")
                            sfx_clear = gr.Button("Remove sound")
                media_df = gr.Dataframe(headers=["Scene", "File", "Type", "Status"], interactive=False, max_height=500)
                to_review = gr.Button("Continue to Review & Export →", variant="primary")
            # ---------------- step 5
            with gr.Tab("5. Review & Export", id="review") as tab5:
                review = gr.HTML(elem_id="review")
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Fix a scene")
                        scene_pick = gr.Dropdown(label="Scene", choices=[])
                        scene_info = gr.Markdown(elem_id="scene-info")
                        with gr.Row():
                            n1 = gr.Button("−0.5 s")
                            n2 = gr.Button("−0.1 s")
                            n3 = gr.Button("+0.1 s")
                            n4 = gr.Button("+0.5 s")
                        with gr.Row():
                            start_box = gr.Number(label="Start time (seconds)", precision=3)
                            set_start = gr.Button("Set start")
                            reset_start = gr.Button("Back to detected")
                        swap_file = gr.File(label="Swap this scene's image/clip", file_types=[
                            ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"])
                        swap_btn = gr.Button("Use the new file for this scene")
                        prev_btn = gr.Button("▶ Preview this scene", variant="secondary")
                    with gr.Column(scale=1):
                        prev_video = gr.Video(label="Scene preview (small, quick)", interactive=False, elem_id="prev-video")
                with gr.Accordion("This project's settings (motion, transitions, captions, audio)", open=False):
                    proj_form = build_settings_form()
                    with gr.Row():
                        proj_save = gr.Button("Save project settings", variant="primary")
                        proj_reset = gr.Button("Reset to the preset")
                gr.Markdown("### Render")
                with gr.Row():
                    resolution = gr.Radio([("1080p (recommended)", "1080p"),
                                           ("4K - very slow on a laptop, about 4x longer", "4K")],
                                          value="1080p", label="Resolution")
                    quality = gr.Radio([("Fast", "fast"), ("Standard", "standard"), ("High (slower)", "high")],
                                       value="standard", label="Quality")
                ready = gr.Markdown()
                with gr.Row():
                    render_btn = gr.Button("🎬 Render video", variant="primary", scale=3)
                    stop_btn = gr.Button("Stop", variant="stop", scale=1)
                render_msg = gr.Markdown(elem_id="render-msg")
                out_video = gr.Video(label="Finished video", interactive=False, elem_id="out-video")
                with gr.Row():
                    open_btn2 = gr.Button("Open output folder")
                    clean_btn = gr.Button("Delete temporary render files (frees disk space)")
            # ---------------- presets
            with gr.Tab("Presets", id="presets") as tab6:
                gr.Markdown("Presets are your channel styles. Changes here apply to **new** projects; an open project "
                            "keeps its own copy (change it in step 5). Saved in `settings/presets.json`.")
                with gr.Row():
                    pr_pick = gr.Dropdown(preset_names, value=preset_names[0], label="Preset")
                    pr_name = gr.Textbox(label="New name (for Duplicate / Rename)")
                with gr.Row():
                    pr_dup = gr.Button("Duplicate")
                    pr_ren = gr.Button("Rename")
                    pr_del = gr.Button("Delete", variant="stop")
                    pr_reset = gr.Button("Restore the 3 original presets")
                pr_form = build_settings_form()
                pr_save = gr.Button("Save preset", variant="primary")

        # ---------------- wiring
        create_btn.click(create_project, [new_name, new_aspect, new_preset], [proj, header, proj_list, tabs]).then(
            load_step2, [proj], [voice_info, script_text, expected, script_df])
        open_btn.click(open_project, [proj_list], [proj, header, tabs]).then(
            load_step2, [proj], [voice_info, script_text, expected, script_df])
        refresh_btn.click(refresh_projects, None, [proj_list])

        tab2.select(load_step2, [proj], [voice_info, script_text, expected, script_df])
        voice_btn.click(save_voice, [proj, voice_files], [voice_info, header])
        script_file.upload(load_script_file, [script_file], [script_text])
        check_btn.click(check_script, [script_text, expected], [script_info, script_df])
        script_btn.click(save_script, [proj, script_text, expected, confirm], [script_info, script_df, tabs]).then(
            load_step3, [proj], [sync_info, sync_df])

        tab3.select(load_step3, [proj], [sync_info, sync_df])
        sync_btn.click(run_sync, [proj, model, language], [sync_info, sync_df, tabs], concurrency_id="heavy",
                       concurrency_limit=1).then(load_step4, [proj], [media_info, media_df])

        tab4.select(load_step4, [proj], [media_info, media_df])
        media_btn.click(add_media, [proj, media_files, media_folder, media_path],
                        [media_info, media_df, media_files, media_folder])
        music_btn.click(lambda f, x: set_audio_extra(f, "music", x), [proj, music_file], [media_info, music_file])
        sfx_btn.click(lambda f, x: set_audio_extra(f, "sfx", x), [proj, sfx_file], [media_info, sfx_file])
        music_clear.click(lambda f: clear_audio_extra(f, "music"), [proj], [media_info])
        sfx_clear.click(lambda f: clear_audio_extra(f, "sfx"), [proj], [media_info])

        step5_out = [review, scene_pick, scene_info, start_box, *proj_form, resolution, quality, ready]
        tab5.select(load_step5, [proj], step5_out)
        to_review.click(lambda: gr.Tabs(selected="review"), None, [tabs]).then(load_step5, [proj], step5_out)
        scene_pick.change(pick_scene, [proj, scene_pick], [scene_info, start_box])
        for btn, d in ((n1, -0.5), (n2, -0.1), (n3, 0.1), (n4, 0.5)):
            btn.click(lambda f, n, d=d: nudge_scene(f, n, d), [proj, scene_pick], [review, scene_info, start_box, ready])
        set_start.click(set_scene_start, [proj, scene_pick, start_box], [review, scene_info, start_box, ready])
        reset_start.click(reset_scene_start, [proj, scene_pick], [review, scene_info, start_box, ready])
        swap_btn.click(swap_media, [proj, scene_pick, swap_file], [review, scene_info, swap_file, ready])
        prev_btn.click(preview_scene, [proj, scene_pick], [prev_video], concurrency_id="heavy", concurrency_limit=1)
        proj_save.click(save_project_settings, [proj, *proj_form], [review, header])
        proj_reset.click(reset_project_settings, [proj], proj_form)
        render_btn.click(do_render, [proj, resolution, quality], [out_video, render_msg], concurrency_id="heavy",
                         concurrency_limit=1).then(load_step4, [proj], [media_info, media_df])
        stop_btn.click(stop_render, None, [render_msg], concurrency_limit=None)
        open_btn2.click(open_output, [proj], None)
        clean_btn.click(clean_temp, [proj], None)

        tab6.select(preset_load, [pr_pick], pr_form)
        pr_pick.change(preset_load, [pr_pick], pr_form)
        pr_save.click(preset_save, [pr_pick, *pr_form], None)
        pr_dup.click(preset_duplicate, [pr_pick, pr_name], [pr_pick, new_preset, pr_name])
        pr_ren.click(preset_rename, [pr_pick, pr_name], [pr_pick, new_preset, pr_name])
        pr_del.click(preset_delete, [pr_pick], [pr_pick, new_preset])
        pr_reset.click(preset_reset, None, [pr_pick, new_preset])
        demo.load(preset_load, [pr_pick], pr_form)
    return demo


def free_port(preferred=7860):
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def main():
    from sceneforge import paths
    demo = build_ui()
    theme = gr.themes.Soft(primary_hue="indigo", font=["Segoe UI", "Arial", "sans-serif"],
                           font_mono=["Consolas", "monospace"])
    port = free_port()
    print(f"\n  SceneForge is running at http://127.0.0.1:{port}  (close this window to stop it)\n")
    demo.queue(default_concurrency_limit=4).launch(
        server_name="127.0.0.1", server_port=port, inbrowser="--no-browser" not in sys.argv,
        share=False, show_error=True, theme=theme, css=CSS, ssr_mode=False,
        allowed_paths=[str(paths.projects_dir())], max_threads=8, quiet=True,
    )


if __name__ == "__main__":
    main()
