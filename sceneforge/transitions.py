"""Scene transitions, centred on the scene boundary.

A transition of length 2h frames covers [boundary - h, boundary + h). The outgoing scene is extended by
h frames past the boundary and the incoming scene starts h frames early, so the total length never
changes and each scene is exactly half-way in when its first word is spoken.
"""
import random

import cv2
import numpy as np

from .presets import TRANSITION_TYPES


def plan_transitions(n_boundaries, settings, seed):
    t = settings["transitions"]
    mode = t.get("mode", "rotate")
    if mode == "cut":
        return ["cut"] * n_boundaries
    if mode == "lock":
        return [t.get("lock_type") or "fade"] * n_boundaries
    types = [x for x in t.get("types") or [] if x in TRANSITION_TYPES] or ["fade"]
    out, prev = [], None
    rng = random.Random(f"{seed}:transitions")
    for _ in range(n_boundaries):
        choices = [x for x in types if x != prev] or types
        prev = rng.choice(choices)
        out.append(prev)
    return out


def _ease(q):
    return q * q * (3 - 2 * q)


def _scale_center(img, z):
    if abs(z - 1.0) < 1e-4:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2 - 0.5, h / 2 - 0.5), 0, z)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def blend(kind, A, B, q):
    """Combine outgoing frame A and incoming frame B at progress q (0..1)."""
    e = _ease(q)
    if kind == "fade":
        return cv2.addWeighted(A, 1.0 - e, B, e, 0.0)
    h, w = A.shape[:2]
    if kind in ("slide_left", "slide_right"):
        x = int(round(e * w))
        out = np.empty_like(A)
        if kind == "slide_left":   # new picture pushes in from the right, old one leaves to the left
            out[:, :w - x] = A[:, x:]
            out[:, w - x:] = B[:, :x]
        else:                      # new picture pushes in from the left
            out[:, x:] = A[:, :w - x]
            out[:, :x] = B[:, w - x:]
        return out
    if kind == "zoom_in":
        # Old picture rushes towards the camera and dissolves into the new one.
        a = _scale_center(A, 1.0 + 0.35 * e)
        b = _scale_center(B, 1.0 + 0.15 * (1 - e))
        return cv2.addWeighted(a, 1.0 - e, b, e, 0.0)
    if kind == "zoom_out":
        # New picture starts close-up and settles back while the old one fades away.
        a = A
        b = _scale_center(B, 1.0 + 0.35 * (1 - e))
        return cv2.addWeighted(a, 1.0 - e, b, e, 0.0)
    return B if q >= 0.5 else A
