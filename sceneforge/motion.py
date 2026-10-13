"""Keyframed camera motion for still images (Ken Burns), with seeded variety per scene."""
import math
import random

EASINGS = {
    "linear": lambda p: p,
    "ease_in_out": lambda p: p * p * (3 - 2 * p),
    "ease_in_out_sine": lambda p: 0.5 - 0.5 * math.cos(math.pi * p),
    "ease_out": lambda p: 1 - (1 - p) * (1 - p),
}


def plan_motions(scene_numbers, image_scenes, settings, seed):
    """Return {scene_number: motion dict} for image scenes.

    Never repeats the previous scene's movement; zoom amount, pan distance and easing vary per scene.
    A fixed seed per project makes every re-render identical.
    """
    m = settings["motion"]
    types = [t for t in m.get("types") or [] if t] or ["zoom_in", "zoom_out"]
    easings = [e for e in m.get("easing") or [] if e in EASINGS] or ["ease_in_out"]
    zmin, zmax = sorted((float(m["zoom_min"]), float(m["zoom_max"])))
    pmin, pmax = sorted((float(m["pan_min"]), float(m["pan_max"])))
    zmin = max(1.01, zmin)
    zmax = max(zmin, zmax)
    plans = {}
    prev_type = None
    for n in scene_numbers:
        rng = random.Random(f"{seed}:{n}:motion")
        choices = [t for t in types if t != prev_type] or types
        t = rng.choice(choices)
        prev_type = t
        if n not in image_scenes:
            continue
        zoom = rng.uniform(zmin, zmax)
        pan = rng.uniform(pmin, pmax)
        direction = rng.choice([-1, 1])
        vdrift = rng.uniform(-0.35, 0.35)
        easing = rng.choice(easings)
        plan = {"type": t, "easing": easing}
        if t == "zoom_in":
            plan.update(z0=1.0, z1=zoom, x0=0, y0=0, x1=0, y1=0)
        elif t == "zoom_out":
            plan.update(z0=zoom, z1=1.0, x0=0, y0=0, x1=0, y1=0)
        elif t in ("pan_left", "pan_right"):
            # Constant zoom just big enough to have room to pan.
            zp = max(zoom, 1.0 / (1.0 - pan) + 0.01)
            sgn = 1 if t == "pan_right" else -1  # camera moves right -> picture slides left
            plan.update(z0=zp, z1=zp, x0=-sgn * pan / 2, x1=sgn * pan / 2, y0=0, y1=0)
        elif t == "zoom_in_pan":
            reach = min(pan, (1 - 1 / zoom)) * 0.95
            plan.update(z0=1.0, z1=zoom, x0=0, y0=0, x1=direction * reach / 2,
                        y1=vdrift * reach / 2)
        elif t == "zoom_out_pan":
            reach = min(pan, (1 - 1 / zoom)) * 0.95
            plan.update(z0=zoom, z1=1.0, x0=direction * reach / 2, y0=vdrift * reach / 2, x1=0, y1=0)
        plans[n] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in plan.items()}
    return plans


def camera_at(plan, p):
    """Zoom and centre offset (fractions of the frame) at progress p in [0, 1]."""
    e = EASINGS.get(plan["easing"], EASINGS["linear"])(min(1.0, max(0.0, p)))
    z0, z1 = plan["z0"], plan["z1"]
    z = z0 * (z1 / z0) ** e  # geometric: zoom speed looks constant
    x = plan["x0"] + (plan["x1"] - plan["x0"]) * e
    y = plan["y0"] + (plan["y1"] - plan["y0"]) * e
    return z, x, y
