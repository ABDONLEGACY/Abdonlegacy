"""Scene-by-scene renderer.

The timeline is cut into small pieces: the "body" of each scene and each transition. Every piece is
encoded to its own file, so memory use stays low and an interrupted render resumes where it stopped
(finished pieces are reused if nothing that affects them has changed). Finally the pieces are joined
without re-encoding and the mixed audio is added.

Sync guarantee: scene k starts at frame B[k] = round(start_k * fps). A transition across boundary B
covers [B - h, B + h), using frames from BOTH neighbouring scenes (each scene is extended by h frames on
that side), so the total video length is exactly the voiceover length and no scene start moves.
"""
import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import audio as audiomod
from . import ffmpeg_utils as ff
from .captions import CaptionRenderer
from .media import media_kind
from .motion import plan_motions
from .sources import ImageSource, VideoSource
from .transitions import blend, plan_transitions
from . import effects, film
from . import sfx as builtin_sfx
from .paths import safe_replace, safe_unlink

FPS = 30
QUALITY = {"fast": ("superfast", 21), "standard": ("veryfast", 19), "high": ("medium", 17)}
RENDER_VERSION = 3
CHUNK_FRAMES = 300  # neighbouring pieces are encoded together in ~10 s chunks (fewer encoder start-ups)  # bump to invalidate all cached pieces after an engine change


class Stopped(Exception):
    pass


STOP = threading.Event()


def fmt_time(s):
    s = max(0, int(round(s)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {sec:02d}s" if m else f"{sec}s")


class Timeline:
    """All frame-exact decisions for a render: scene boundaries, transitions, motions, pieces."""

    def __init__(self, project, W, H, fps=FPS, focus=None):
        self.p, self.W, self.H, self.fps = project, W, H, fps
        st = project.settings
        tl = project.timeline()
        if not tl:
            raise ValueError("The project has no scenes yet.")
        dur = float(project.data["audio_duration"])
        self.N = int(round(dur * fps))
        self.n = len(tl)
        B = [0] + [int(round(r["start"] * fps)) for r in tl[1:]] + [self.N]
        for i in range(1, len(B)):
            if B[i] <= B[i - 1]:
                raise ValueError(f"Scene {tl[i - 1]['number']} has no length - check its start time in the review table.")
        self.B = B
        lens = [B[i + 1] - B[i] for i in range(self.n)]
        self.numbers = [r["number"] for r in tl]
        seed = project.data["seed"]
        tcfg = st["transitions"]
        half = 0 if tcfg.get("mode") == "cut" else int(round(float(tcfg.get("duration", 0.5)) * fps / 2))
        self.types = plan_transitions(self.n - 1, st, seed)
        self.h = []
        tear_half = int(round(film.TEAR_LEN * fps / 2))
        for k in range(self.n - 1):
            nxt = project.scene(self.numbers[k + 1]) or {}
            if nxt.get("chapter"):
                # [CHAPTER]: this scene opens with the paper tear (whatever the normal transition is)
                self.types[k] = "tear"
                hk = max(1, min(tear_half, lens[k] // 2 - 1, lens[k + 1] // 2 - 1))
            else:
                hk = 0 if self.types[k] == "cut" else min(half, lens[k] // 4, lens[k + 1] // 4)
            self.h.append(hk)
        self.ext = []
        for k in range(self.n):
            e0 = B[k] - (self.h[k - 1] if k > 0 else 0)
            e1 = B[k + 1] + (self.h[k] if k < self.n - 1 else 0)
            self.ext.append((e0, e1))
        # media
        self.media = []
        image_scenes = set()
        for num in self.numbers:
            sc = project.scene(num)
            path = project.path(sc.get("media")) if sc and sc.get("media") else None
            if path is not None and not path.exists():
                path = None
            kind = media_kind(path) if path else ""
            self.media.append((path, kind))
            if kind != "video":
                image_scenes.add(num)
        self.motions = plan_motions(self.numbers, image_scenes, st, seed)
        # {scene number: [pin / text effects with position, tilt and trigger time]} - only synced effects render
        # a preview only needs the effects of the previewed scene and its neighbours (transitions)
        only = None
        if focus is not None and focus in self.numbers:
            k = self.numbers.index(focus)
            only = set(self.numbers[max(0, k - 1):k + 2])
        self.effects = {n: [e for e in items if e["t"] is not None]
                        for n, items in effects.resolve(project, only=only).items()}
        self.effects = {n: items for n, items in self.effects.items() if items}
        # pieces
        self.pieces = []
        for k in range(self.n):
            f0 = B[k] + (self.h[k - 1] if k > 0 else 0)
            f1 = B[k + 1] - (self.h[k] if k < self.n - 1 else 0)
            if f1 > f0:
                self.pieces.append({"kind": "body", "k": k, "f0": f0, "f1": f1})
            if k < self.n - 1 and self.h[k] > 0:
                self.pieces.append({"kind": "trans", "k": k, "f0": B[k + 1] - self.h[k], "f1": B[k + 1] + self.h[k],
                                    "type": self.types[k]})

    def missing_media(self):
        return [self.numbers[k] for k, (p, _) in enumerate(self.media) if p is None]

    def scene_desc(self, k):
        path, kind = self.media[k]
        d = {"num": self.numbers[k], "ext": self.ext[k], "kind": kind}
        if path is not None:
            st = path.stat()
            d.update(path=str(path), size=st.st_size, mtime=int(st.st_mtime))
        if kind == "video":
            c = self.p.settings["clips"]
            d.update(fit=c["fit_mode"], slow=c["max_slowdown"])
        else:
            d["motion"] = self.motions.get(self.numbers[k])
        fx = self.effects.get(self.numbers[k])
        if fx:  # only scenes with effects carry these, so other scenes' finished parts stay valid
            d["effects"] = fx
            d["effects_style"] = self.p.settings.get("effects")
        return d


class EffectSource:
    """Wraps a scene's frame source and draws its pins / text on every frame, locked to the picture."""

    def __init__(self, src, layer):
        self.src, self.layer = src, layer

    def frames(self, a, b):
        for k, fr in enumerate(self.src.frames(a, b), start=a):
            fr = np.array(fr)  # writable copy
            self.layer.draw(fr, k, self.src.project)
            dx, dy = self.layer.shake(k)
            yield film.apply_shake(fr, dx, dy)

    def close(self):
        self.src.close()


class Renderer:
    def __init__(self, project, resolution=None, quality=None, progress=None, size=None, tag=None, focus=None):
        self.p = project
        self.resolution = resolution or project.data.get("render", {}).get("resolution", "1080p")
        self.quality = quality or project.data.get("render", {}).get("quality", "standard")
        self.W, self.H = size or project.size(self.resolution)
        self.fps = FPS
        self.progress = progress or (lambda f, m: None)
        self.tl = Timeline(project, self.W, self.H, self.fps, focus=focus)
        self.tag = tag or f"{self.W}x{self.H}"
        self.dir = project.work_dir / f"render_{self.tag}"
        self.piece_dir = self.dir / "pieces"
        self.clip_dir = project.work_dir / f"clips_{self.W}x{self.H}"
        self.piece_dir.mkdir(parents=True, exist_ok=True)
        cap_cfg = project.settings["captions"]
        self.captions = CaptionRenderer(project.words(), cap_cfg, self.W, self.H, self.fps)
        self._sources = {}
        self.style = {**effects.DEFAULT_STYLE, **(project.settings.get("effects") or {})}
        self.finish = film.Finish(self.W, self.H) if self.style.get("finish") else None

    # ---- sources -------------------------------------------------------------
    def _placeholder(self, k):
        f = self.p.work_dir / f"missing_{self.tl.numbers[k]}.png"
        if not f.exists():
            from . import fonts
            img = Image.new("RGB", (1280, 720), (24, 24, 28))
            ImageDraw.Draw(img).text((640, 360), f"Scene {self.tl.numbers[k]}: media missing", fill=(200, 80, 80),
                                     anchor="mm", font=fonts.load("Arial Bold", 48))
            img.save(f)
        return f

    def source(self, k):
        if k in self._sources:
            return self._sources[k]
        for old in [x for x in self._sources if x < k - 1]:
            self._sources.pop(old).close()
        path, kind = self.tl.media[k]
        e0, e1 = self.tl.ext[k]
        length = e1 - e0
        if kind == "video":
            c = self.p.settings["clips"]
            src = VideoSource(path, self.W, self.H, self.fps, length, self.clip_dir, c["fit_mode"],
                              float(c["max_slowdown"]))
        else:
            plan = self.tl.motions[self.tl.numbers[k]]
            src = ImageSource(path or self._placeholder(k), self.W, self.H, length, plan)
        fx = self.tl.effects.get(self.tl.numbers[k])
        if fx:  # only scenes with effects take the (slower) overlay path
            cap = self.p.settings.get("captions", {})
            src = EffectSource(src, effects.EffectLayer(
                fx, self.p.settings.get("effects"), self.W, self.H, self.fps, e0, end_s=self.tl.B[k + 1] / self.fps,
                captions_bottom=bool(cap.get("enabled")) and cap.get("position", "bottom") == "bottom"))
        self._sources[k] = src
        return src

    def close(self):
        for s in self._sources.values():
            s.close()
        self._sources.clear()

    # ---- pieces ----------------------------------------------------------------
    def piece_sig(self, pc):
        k = pc["k"]
        d = {"v": RENDER_VERSION, "piece": pc, "W": self.W, "H": self.H, "fps": self.fps, "q": self.quality,
             "scene": self.tl.scene_desc(k), "caps": self.captions.signature(pc["f0"], pc["f1"]),
             "finish": bool(self.finish), "end": self.tl.B[k + 1]}
        if pc["kind"] == "trans":
            d["next"] = self.tl.scene_desc(k + 1)
        return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()

    def _encoder(self, out_path):
        preset, crf = QUALITY.get(self.quality, QUALITY["standard"])
        args = ["-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{self.W}x{self.H}", "-r", str(self.fps), "-i", "-",
                "-an", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-g", str(self.fps * 2),
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-video_track_timescale", str(self.fps * 1000), "-f", "mp4", str(out_path)]
        return ff.popen(args, stdin=subprocess.PIPE)

    def _frames_for(self, pc):
        k, f0, f1 = pc["k"], pc["f0"], pc["f1"]
        e0 = self.tl.ext[k][0]
        if pc["kind"] == "body":
            for i, fr in enumerate(self.source(k).frames(f0 - e0, f1 - e0)):
                yield f0 + i, fr
            return
        n0 = self.tl.ext[k + 1][0]
        a_iter = self.source(k).frames(f0 - e0, f1 - e0)
        a_frames = [np.array(f) for f in a_iter]  # at most a second of frames
        b_iter = self.source(k + 1).frames(f0 - n0, f1 - n0)
        total = f1 - f0
        tear = film.Tear(a_frames[0], seed=self.p.data["seed"] + k) if pc["type"] == "tear" and a_frames else None
        for i, (A, Bf) in enumerate(zip(a_frames, b_iter)):
            q = (i + 0.5) / total
            yield f0 + i, (tear.draw(np.asarray(Bf), q) if tear else blend(pc["type"], A, Bf, q))

    def chunks(self, pieces):
        """Group consecutive pieces into ~10 s chunks. Each chunk is one encoded file that can be reused."""
        out, cur, frames = [], [], 0
        for i, pc in pieces:
            cur.append((i, pc))
            frames += pc["f1"] - pc["f0"]
            if frames >= CHUNK_FRAMES:
                out.append(cur)
                cur, frames = [], 0
        if cur:
            out.append(cur)
        return out

    def chunk_path(self, members):
        first, last = members[0][0], members[-1][0]
        return self.piece_dir / f"{first:05d}-{last:05d}.mp4"

    def render_chunk(self, members, out_path, on_frame=None):
        tmp = out_path.with_name(out_path.stem + ".part.mp4")
        proc = self._encoder(tmp)
        count = 0
        expected = sum(pc["f1"] - pc["f0"] for _, pc in members)
        try:
            for _, pc in members:
                for gidx, fr in self._frames_for(pc):
                    if STOP.is_set():
                        raise Stopped()
                    if not fr.flags.writeable or not fr.flags.c_contiguous:
                        fr = np.array(fr)
                    if self.finish is not None:
                        fr = self.finish.apply(fr, gidx)
                    self.captions.draw(fr, gidx)
                    proc.stdin.write(memoryview(fr))
                    count += 1
                    if on_frame:
                        on_frame()
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            proc.wait()
            raise ff.FFmpegError("Video encoder stopped: " + ff.stderr_text(proc))
        except BaseException:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.kill()
            proc.wait()
            safe_unlink(tmp)
            raise
        rc = proc.wait()
        if rc != 0:
            raise ff.FFmpegError("Video encoder failed: " + ff.stderr_text(proc))
        if count != expected:
            raise RuntimeError(f"Part {out_path.name}: produced {count} frames, expected {expected}")
        safe_replace(tmp, out_path)

    def render_video(self, pieces=None, w_start=0.0, w_span=1.0):
        """Render (or reuse) all chunks of pieces, then join them. Returns path of the silent video."""
        full = pieces is None
        pieces = list(enumerate(self.tl.pieces)) if full else pieces
        chunks = self.chunks(pieces)
        todo, total_frames, keep = [], 0, set()
        for members in chunks:
            out = self.chunk_path(members)
            sig = hashlib.sha1("|".join(self.piece_sig(pc) for _, pc in members).encode()).hexdigest()
            sig_file = out.with_suffix(".json")
            keep.update((out.name, sig_file.name))
            done = out.exists() and sig_file.exists() and sig_file.read_text() == sig
            if not done:
                todo.append((members, out, sig, sig_file))
                total_frames += sum(pc["f1"] - pc["f0"] for _, pc in members)
        reused = len(chunks) - len(todo)
        t_start = time.time()
        state = {"done": 0, "last": 0.0}

        def on_frame():
            state["done"] += 1
            now = time.time()
            if now - state["last"] < 0.5:
                return
            state["last"] = now
            frac = state["done"] / max(1, total_frames)
            el = now - t_start
            eta = el / max(1e-6, frac) - el if state["done"] > 15 else None
            msg = f"Rendering frames {state['done']}/{total_frames}"
            if reused:
                msg += f" ({reused} finished parts reused)"
            if eta is not None:
                msg += f" - about {fmt_time(eta)} left"
            self.progress(w_start + w_span * 0.95 * frac, msg)

        self.progress(w_start, f"Rendering {len(todo)} of {len(chunks)} parts ({reused} already done)")
        try:
            for members, out, sig, sig_file in todo:
                safe_unlink(sig_file)
                self.render_chunk(members, out, on_frame)
                sig_file.write_text(sig)
        finally:
            self.close()
        if full:
            # a full render: remove leftover parts from older timings so they don't fill the disk
            for f in self.piece_dir.iterdir():
                if f.name not in keep and not f.name.endswith(".part.mp4"):
                    safe_unlink(f, tries=1)
        # join
        self.progress(w_start + w_span * 0.96, "Joining parts ...")
        listing = self.dir / ("pieces_%d.txt" % os.getpid())
        lines = []
        for members in chunks:
            rel = self.chunk_path(members).resolve().as_posix().replace("'", "'\\''")
            lines.append(f"file '{rel}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        video = self.dir / "video_only.mp4"
        ff.run_to(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart"],
                  video, desc="Joining video parts")
        safe_unlink(listing)
        return video

    # ---- audio -------------------------------------------------------------------
    def build_audio(self, t0, t1, out_path):
        """Voice + clip sound effects + whooshes + ducked music, for the time range [t0, t1)."""
        p, st = self.p, self.p.settings
        dur = t1 - t0
        voice = p.work_dir / "voice.wav"
        if not voice.exists():
            raise FileNotFoundError("Joined voiceover not found - go back to step 2 and save the voiceover again.")
        # unique scratch file: on Windows a memory-mapped file from an earlier run may still be locked
        fx = audiomod.Track(self.dir / f"fx_track_{os.getpid()}_{int(time.time() * 1000)}.npy", dur)
        used = False
        clips = st["clips"]
        if clips.get("keep_audio"):
            vol = float(clips.get("clip_volume", 0.25))
            for k, (path, kind) in enumerate(self.tl.media):
                if kind != "video":
                    continue
                e0, e1 = self.tl.ext[k]
                s0, s1 = e0 / self.fps, e1 / self.fps
                if s1 <= t0 or s0 >= t1:
                    continue
                info = ff.video_info(path)
                if not info["has_audio"]:
                    continue
                from .sources import clip_fit
                fit = clip_fit(info["duration"], e1 - e0, self.fps, clips["fit_mode"], float(clips["max_slowdown"]))
                real = fit["real_frames"] / self.fps
                filt = f"atempo={fit['speed']:.6f}" if abs(fit["speed"] - 1) > 1e-4 else None
                samples = ff.read_audio_f32(path, sr=audiomod.SR, duration_s=None, filters=filt)[:int(real * audiomod.SR)]
                fin = 2 * self.tl.h[k - 1] / self.fps if k > 0 else 0.0
                fout = 2 * self.tl.h[k] / self.fps if k < self.tl.n - 1 else 0.3
                if fit["fill"]:
                    fout = max(fout, 0.4)
                samples = audiomod.fade(samples, max(fin, 0.02), max(fout, 0.05))
                fx.add(s0 - t0, samples, vol)
                used = True
        sfx = p.path(p.data.get("sfx"))
        if sfx and sfx.exists() and any(h > 0 for h in self.tl.h):
            whoosh = ff.read_audio_f32(sfx, sr=audiomod.SR)
            wl = len(whoosh) / audiomod.SR
            vol = float(st["audio"].get("sfx_volume", 0.6))
            for k, h in enumerate(self.tl.h):
                if h <= 0:
                    continue
                b = self.tl.B[k + 1] / self.fps
                start = b - min(wl / 2, h / self.fps * 1.5)
                if start + wl <= t0 or start >= t1:
                    continue
                fx.add(start - t0, whoosh, vol)
                used = True
        # scene effect sounds (pin drop / text pop), exactly at each effect's word
        snd = effects.sound_settings()
        cache = {}
        for items in self.tl.effects.values():
            for e in items:
                cfg = snd.get(e["type"])
                if not cfg or not cfg["path"] or not (t0 - 2 <= e["t"] < t1):
                    continue
                if e["type"] not in cache:
                    cache[e["type"]] = ff.read_audio_f32(cfg["path"], sr=audiomod.SR)
                fx.add(e["t"] - t0, cache[e["type"]], cfg["volume"])
                used = True
            # the optional "marker scribble" while the underline draws itself
            line = snd.get("underline")
            est = {**effects.DEFAULT_STYLE, **(st.get("effects") or {})}
            if line and line["path"] and est.get("text_style") == "hand_underline" and est.get("underline", True):
                for e in items:
                    if e["type"] == "text" and t0 - 2 <= e["t"] < t1:
                        if "underline" not in cache:
                            cache["underline"] = ff.read_audio_f32(line["path"], sr=audiomod.SR)
                        fx.add(e["t"] + effects.LINE_DELAY - t0, cache["underline"], line["volume"])
                        used = True
        # built-in sounds: premium effects, paper tears, soft whooshes on hard cuts
        for when, name, gain in self.builtin_events():
            if t0 - 2 <= when < t1:
                fx.add(when - t0, builtin_sfx.get(name), gain)
                used = True
        fx_wav = None
        if used:
            fx_wav = self.dir / "fx_track.wav"
            fx.to_wav(fx_wav, dur)
        else:
            fx.discard()
        voice_in = voice
        if t0 > 0 or t1 < p.data["audio_duration"] - 1e-3:
            voice_in = self.dir / "voice_part.wav"
            ff.run_to(["-ss", f"{t0:.4f}", "-t", f"{dur:.4f}", "-i", str(voice), "-c:a", "pcm_s16le"], voice_in,
                      desc="Cutting voice")
        music = p.path(p.data.get("music"))
        music = music if music and music.exists() else None
        audiomod.final_mix(voice_in, fx_wav, out_path, dur, music=music,
                           music_volume=float(st["audio"].get("music_volume", 0.15)),
                           duck=bool(st["audio"].get("duck", True)))
        return out_path

    def builtin_events(self):
        """[(time s, built-in sound name, gain)] for the whole video (effects, paper tears, cut whooshes)."""
        if hasattr(self, "_events"):
            return self._events
        out = []
        user = {k: bool(v["path"]) for k, v in effects.sound_settings().items()}
        k_of = {n: k for k, n in enumerate(self.tl.numbers)}
        for num, items in self.tl.effects.items():
            k = k_of.get(num)
            end_s = self.tl.B[k + 1] / self.fps if k is not None else None
            out += effects.builtin_sound_events(items, self.style, end_s, user)
        for k, typ in enumerate(self.tl.types):
            b = self.tl.B[k + 1] / self.fps
            if typ == "tear":
                start = b - self.tl.h[k] / self.fps
                out += [(start, "tear", 1.0), (start - 0.1, "whoosh", 1.0)]
            elif self.tl.h[k] == 0 and self.style.get("cut_whoosh"):
                out.append((b - 0.21, "whoosh_soft", 1.0))
        self._events = sorted(out)
        return self._events

    def audio_sig(self, t0, t1):
        """Hash of everything the mixed audio depends on, so an unchanged mix is reused (big projects)."""
        p, st = self.p, self.p.settings

        def fstat(path):
            if not path or not Path(path).exists():
                return None
            s_ = Path(path).stat()
            return [str(path), s_.st_size, int(s_.st_mtime)]
        clips = []
        if st["clips"].get("keep_audio"):
            for k, (path, kind) in enumerate(self.tl.media):
                if kind == "video":
                    clips.append([k, fstat(path), self.tl.ext[k]])
        d = {"v": RENDER_VERSION, "range": [round(t0, 4), round(t1, 4)], "voice": fstat(p.work_dir / "voice.wav"),
             "music": fstat(p.path(p.data.get("music"))), "sfx": fstat(p.path(p.data.get("sfx"))),
             "audio": st["audio"], "clips_cfg": st["clips"], "clips": clips, "fps": self.fps,
             "whoosh": [[self.tl.B[k + 1], h] for k, h in enumerate(self.tl.h) if h > 0] if p.data.get("sfx") else [],
             "effects": [[e["type"], e["t"]] for items in self.tl.effects.values() for e in items],
             "effect_style": [st.get("effects", {}).get(k) for k in ("text_style", "underline")],
             "effect_sounds": {k: [fstat(v["path"]), v["volume"]] for k, v in effects.sound_settings().items()},
             "builtin": hashlib.sha1(json.dumps(self.builtin_events()).encode()).hexdigest()}
        return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()

    # ---- top level ---------------------------------------------------------------
    def run(self):
        STOP.clear()
        t0 = time.time()
        audio_out = self.dir / "audio.m4a"
        sig = self.audio_sig(0.0, self.tl.N / self.fps)
        sig_file = audio_out.with_suffix(".json")
        if audio_out.exists() and sig_file.exists() and sig_file.read_text() == sig:
            self.progress(0.0, "Audio unchanged - reusing it")
        else:
            self.progress(0.0, "Preparing audio (voice, clip sounds, music) ...")
            safe_unlink(sig_file)
            self.build_audio(0.0, self.tl.N / self.fps, audio_out)
            sig_file.write_text(sig)
        opening = self.render_opening()
        video = self.render_video(w_start=0.06 if opening else 0.04, w_span=0.90 if opening else 0.92)
        self.progress(0.97, "Adding sound ...")
        if opening:
            video, audio_out = self.join_opening(opening, video, audio_out)
        name = self.p.data["name"]
        suffix = "" if self.resolution == "1080p" else f"_{self.resolution}"
        out = self.p.output_dir / f"{_safe_file(name)}{suffix}.mp4"
        tmp = out.with_name(out.stem + ".part.mp4")
        ff.run(["-i", str(video), "-i", str(audio_out), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
                "-movflags", "+faststart", str(tmp)], desc="Adding audio to video")
        try:
            safe_replace(tmp, out, tries=20)
        except PermissionError:
            # The old video is open in a player (Windows locks it): save next to it under a new name.
            n = 2
            while out.with_name(f"{out.stem} ({n}).mp4").exists():
                n += 1
            out = out.with_name(f"{out.stem} ({n}).mp4")
            safe_replace(tmp, out)
        self.progress(1.0, f"Finished in {fmt_time(time.time() - t0)}")
        return out

    # ---- the typewriter opening ([OPENING: title | stamp] in the script) --------------------------------
    def render_opening(self):
        """Render (or reuse) the opening title: returns (video path, audio wav path) or None."""
        op = self.p.data.get("opening")
        if not op or not op.get("title") or not self.tl.pieces:
            return None
        O = film.Opening(op["title"], op.get("stamp", ""), self.W, self.H)
        first_piece = self.tl.pieces[0]
        sig = hashlib.sha1(json.dumps({"v": RENDER_VERSION, "op": op, "W": self.W, "H": self.H, "fps": self.fps,
                                       "q": self.quality, "finish": bool(self.finish),
                                       "first": self.piece_sig(first_piece)}, sort_keys=True, default=str)
                           .encode()).hexdigest()
        video, wav, sig_file = self.dir / "opening.mp4", self.dir / "opening.wav", self.dir / "opening.json"
        if video.exists() and wav.exists() and sig_file.exists() and sig_file.read_text() == sig:
            return video, wav
        self.progress(0.02, "Typing the opening title ...")
        safe_unlink(sig_file)
        try:
            first = np.array(next(iter(self._frames_for(first_piece)))[1])  # scene 1's first frame, under the tear
        finally:
            self.close()
        nf = int(round(O.duration * self.fps))
        tear = film.Tear(O.page(O.tear_t), seed=self.p.data["seed"])
        tmp = video.with_name("opening.part.mp4")
        proc = self._encoder(tmp)
        try:
            for f in range(nf):
                if STOP.is_set():
                    raise Stopped()
                t = f / self.fps
                fr = O.page(t) if t < O.tear_t else tear.draw(first, min(1.0, (t - O.tear_t + 0.5 / self.fps) / film.TEAR_LEN))
                if self.finish is not None:
                    fr = self.finish.apply(np.ascontiguousarray(fr), f)
                proc.stdin.write(memoryview(np.ascontiguousarray(fr)))
            proc.stdin.close()
        except BaseException:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.kill()
            proc.wait()
            safe_unlink(tmp)
            raise
        if proc.wait() != 0:
            raise ff.FFmpegError("Video encoder failed (opening): " + ff.stderr_text(proc))
        safe_replace(tmp, video)
        # its sounds: a clack per letter, the bell, the stamp, the tear
        import random
        rng = random.Random(7)
        track = audiomod.Track(self.dir / f"opening_track_{os.getpid()}.npy", nf / self.fps)
        for when, name in O.events:
            gain = rng.uniform(0.75, 1.0) if name == "clack" else 1.0
            track.add(when + (rng.uniform(-0.006, 0.006) if name == "clack" else 0.0), builtin_sfx.get(name), gain)
        track.to_wav(wav, nf / self.fps)
        sig_file.write_text(sig)
        return video, wav

    def join_opening(self, opening, video, audio):
        """Put the opening in front of the video and its sounds in front of the mixed audio."""
        op_video, op_wav = opening
        listing = self.dir / ("with_opening_%d.txt" % os.getpid())
        listing.write_text("".join(f"file '{Path(x).resolve().as_posix()}'\n" for x in (op_video, video)),
                           encoding="utf-8")
        joined = self.dir / "video_with_opening.mp4"
        ff.run_to(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart"], joined,
                  desc="Adding the opening")
        safe_unlink(listing)
        joined_audio = self.dir / "audio_with_opening.m4a"
        sr = audiomod.SR
        ff.run_to(["-i", str(op_wav), "-i", str(audio), "-filter_complex",
                   f"[0:a]aresample={sr},aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
                   f"[1:a]aresample={sr},aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
                   "[a0][a1]concat=n=2:v=0:a=1[out]", "-map", "[out]", "-c:a", "aac", "-b:a", "192k"],
                  joined_audio, desc="Adding the opening sounds")
        return joined, joined_audio

    def preview(self, number):
        """Short preview of one scene (with its transitions in and out), at low resolution."""
        STOP.clear()
        k = self.tl.numbers.index(number)
        e0, e1 = self.tl.ext[k]
        pieces = [(i, pc) for i, pc in enumerate(self.tl.pieces)
                  if pc["f0"] >= e0 and pc["f1"] <= e1]
        video = self.render_video(pieces=pieces, w_start=0.0, w_span=0.85)
        audio_out = self.dir / "preview_audio.m4a"
        self.build_audio(e0 / self.fps, e1 / self.fps, audio_out)
        # A new file name every time: on Windows a preview that the browser is still reading can't be
        # overwritten. Older previews of this scene are removed when possible.
        stamp = time.strftime("%H%M%S") + f"{int(time.time() * 1000) % 1000:03d}"
        out = self.p.work_dir / f"preview_scene_{number}_{stamp}.mp4"
        for old in self.p.work_dir.glob(f"preview_scene_{number}_*.mp4"):
            try:
                old.unlink()
            except OSError:
                pass  # still open in the browser - it is cleaned up next time
        ff.run(["-i", str(video), "-i", str(audio_out), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
                "-shortest", "-movflags", "+faststart", str(out)], desc="Making preview")
        self.progress(1.0, "Preview ready")
        return out


def _safe_file(name):
    import re
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip() or "video"
