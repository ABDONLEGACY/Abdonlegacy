"""Built-in sound effects, made with numpy (no files needed): soft, short and clean.

Used by the premium effects (stamps, typewriter text, sticky notes, marker circles, quote cards, paper-tear
chapters, the typewriter opening) and, when a preset turns on "built-in sounds", by pins and text too.
A sound you upload in Settings -> Effect sounds always wins over the built-in one.
"""
import numpy as np

SR = 48000
NAMES = ["pop", "scribble", "pin_thud", "whoosh", "whoosh_soft", "bell", "clack", "stamp", "tear", "swish"]

# level of each built-in sound in the mix (linear gain; the voice peaks near 1.0)
GAIN = {"pop": 0.16, "scribble": 0.11, "pin_thud": 0.26, "whoosh": 0.10, "whoosh_soft": 0.045, "bell": 0.16,
        "clack": 0.085, "stamp": 0.34, "tear": 0.15, "swish": 0.10}

_CACHE = {}


def _t(sec):
    return np.arange(int(SR * sec)) / SR


def _band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.clip((f - lo * 0.7) / (lo * 0.3 + 1e-9), 0, 1) * np.clip((hi * 1.3 - f) / (hi * 0.3), 0, 1)
    return np.fft.irfft(X * m, len(x))


def _fade(x, a=0.003, b=0.01):
    n1, n2 = int(a * SR), int(b * SR)
    if n1:
        x[:n1] *= np.linspace(0, 1, n1)
    if n2:
        x[-n2:] *= np.linspace(1, 0, n2)
    return x


def _make(name, rng):
    if name == "pop":
        t = _t(0.09)
        f = 700 * np.exp(-t * 25) + 260
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)
        x += 0.15 * _band(rng.standard_normal(len(t)), 1500, 5000) * np.exp(-t * 200)
    elif name == "scribble":
        t = _t(0.38)
        n = _band(rng.standard_normal(len(t)), 1800, 6500)
        strokes = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 7.5 * t + rng.uniform(0, 3)))
        env = np.minimum(1, t / 0.03) * np.minimum(1, (t[-1] - t) / 0.06)
        x = n * strokes * env
    elif name == "pin_thud":
        t = _t(0.32)
        f = 120 * np.exp(-t * 12) + 48
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
        x += 0.25 * _band(rng.standard_normal(len(t)), 200, 1800) * np.exp(-t * 90)
    elif name == "swish":
        t = _t(0.36)
        n = rng.standard_normal(len(t))
        p = t / t[-1]
        x = (_band(n, 900, 2500) * (1 - p) + _band(n, 2500, 7000) * p) * np.sin(np.pi * p) ** 1.5
    elif name == "whoosh":
        t = _t(0.9)
        n = rng.standard_normal(len(t))
        p = t / t[-1]
        x = _band(n, 150, 600) * (1 - p) + _band(n, 600, 1800) * np.sin(np.pi * p) + _band(n, 1800, 4000) * p * 0.5
        x *= np.sin(np.pi * p) ** 2
    elif name == "whoosh_soft":
        t = _t(0.42)
        p = t / t[-1]
        n = rng.standard_normal(len(t))
        x = (_band(n, 250, 1200) * (1 - p) + _band(n, 900, 2600) * p) * np.sin(np.pi * p) ** 2
    elif name == "bell":
        t = _t(1.2)
        x = sum(a * np.sin(2 * np.pi * 1320 * r * t) * np.exp(-t * d)
                for a, r, d in [(1, 1, 3.5), (0.5, 2.76, 6), (0.25, 5.4, 9), (0.15, 0.5, 4)])
    elif name == "clack":
        t = _t(0.09)
        x = _band(rng.standard_normal(len(t)), 1800, 7000) * np.exp(-t * 320)
        x += 0.55 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 70)
        x += 0.18 * np.sin(2 * np.pi * 3300 * t) * np.exp(-t * 120)
        k = int(0.012 * SR)  # second, softer contact (type bar hitting the platen)
        x[k:] += 0.35 * _band(rng.standard_normal(len(t) - k), 600, 3000) * np.exp(-t[:len(t) - k] * 260)
    elif name == "stamp":
        t = _t(0.35)
        f = 95 * np.exp(-t * 18) + 52
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)
        x += 0.55 * _band(rng.standard_normal(len(t)), 250, 3500) * np.exp(-t * 55)
        x += 0.2 * _band(rng.standard_normal(len(t)), 3000, 9000) * np.exp(-t * 300)
    elif name == "tear":
        t = _t(0.65)
        n = _band(rng.standard_normal(len(t)), 900, 7000)
        crackle = np.zeros(len(t))
        idx = rng.choice(len(t), 120, replace=False)
        crackle[idx] = rng.uniform(0.4, 1.0, 120)
        crackle = np.convolve(crackle, np.exp(-np.arange(int(0.012 * SR)) / (0.003 * SR)), "same")
        p = t / t[-1]
        x = n * (0.35 + crackle) * np.minimum(1, p / 0.15) * (1 - p) ** 0.6
    else:
        raise ValueError(name)
    x = _fade(x.astype(np.float64))
    return x / (np.abs(x).max() + 1e-9) * 0.8


def get(name):
    """A built-in sound as a float32 stereo array (n, 2) at 48 kHz, already at its mix level."""
    if name not in _CACHE:
        mono = _make(name, np.random.default_rng(12 + NAMES.index(name))) * GAIN[name]
        _CACHE[name] = np.repeat(mono.astype(np.float32)[:, None], 2, axis=1)
    return _CACHE[name]
