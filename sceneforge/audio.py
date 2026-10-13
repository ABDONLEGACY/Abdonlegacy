"""Voiceover joining and the final audio mix (voice + clip sound + music + transition sounds)."""
from pathlib import Path

import numpy as np

from . import ffmpeg_utils as ff

SR = 48000


def join_voice(files, out_wav):
    """Join one or more voice files (in order) into a single 48 kHz WAV. Returns its duration."""
    files = [Path(f) for f in files]
    if not files:
        raise ValueError("No voiceover file uploaded.")
    args = []
    for f in files:
        args += ["-i", str(f)]
    n = len(files)
    chains = "".join(f"[{i}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];" for i in range(n))
    concat = "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    args += ["-filter_complex", chains + concat, "-map", "[out]", "-c:a", "pcm_s16le", str(out_wav)]
    ff.run(args, desc="Joining voiceover files")
    return ff.duration(out_wav)


class Track:
    """A float32 stereo track on disk (memory-mapped) that clip sounds and effects are added into."""

    def __init__(self, path, seconds):
        self.path = Path(path)
        self.n = int(round(seconds * SR)) + SR
        self.data = np.lib.format.open_memmap(str(self.path), mode="w+", dtype=np.float32, shape=(self.n, 2))
        self.data[:] = 0.0

    def add(self, start_s, samples, gain=1.0):
        i0 = int(round(start_s * SR))
        if i0 >= self.n:
            return
        if i0 < 0:
            samples = samples[-i0:]
            i0 = 0
        m = min(len(samples), self.n - i0)
        if m > 0:
            self.data[i0:i0 + m] += samples[:m] * gain

    def to_wav(self, out_path, seconds):
        n = int(round(seconds * SR))
        raw = self.path.with_suffix(".raw")
        np.clip(self.data[:n], -1.0, 1.0).astype("<f4").tofile(raw)
        ff.run(["-f", "f32le", "-ar", SR, "-ac", 2, "-i", str(raw), "-c:a", "pcm_s16le", str(out_path)],
               desc="Writing effects track")
        raw.unlink(missing_ok=True)
        del self.data
        self.path.unlink(missing_ok=True)


def fade(samples, fade_in_s, fade_out_s):
    n = len(samples)
    if n == 0:
        return samples
    a = int(fade_in_s * SR)
    b = int(fade_out_s * SR)
    env = np.ones(n, dtype=np.float32)
    if a > 0:
        a = min(a, n)
        env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    if b > 0:
        b = min(b, n)
        env[n - b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return samples * env[:, None]


def final_mix(voice_wav, fx_wav, out_path, duration, music=None, music_volume=0.15, duck=True):
    """voice (main) + effects/clip track + optional looped, ducked music -> AAC in .m4a."""
    args = ["-i", str(voice_wav)]
    if fx_wav:
        args += ["-i", str(fx_wav)]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
    fc = []
    idx = 1
    fc.append(f"[0:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[voice][key]")
    mix = ["[voice]"]
    if fx_wav:
        fc.append(f"[{idx}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo[fx]")
        mix.append("[fx]")
        idx += 1
    if music:
        fc.append(f"[{idx}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"atrim=0:{duration:.3f},volume={music_volume:.3f}[mus]")
        if duck:
            # Lower the music while the narration is talking.
            fc.append("[mus][key]sidechaincompress=threshold=0.015:ratio=6:attack=40:release=500:makeup=1[musd]")
        else:
            fc.append("[key]anullsink;[mus]anull[musd]")
        mix.append("[musd]")
    else:
        fc.append("[key]anullsink")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
              f"atrim=0:{duration:.3f}[out]")
    args += ["-filter_complex", ";".join(fc), "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    ff.run(args, desc="Mixing audio")
