"""Read a script (.docx / .txt / .md or pasted text) and split it into scenes."""
import re
from pathlib import Path

# "Scene 1:", "SCENE 2 -", "**Scene 3.**", "## Scene 4", "Scene 5)" ...
SCENE_RE = re.compile(
    r"^[\s#>*_\-]*scene\s*(\d+)\s*(?:[:.\-–—)\]]+|\*\*|\s|$)\s*[*_]*\s*(.*)$",
    re.IGNORECASE,
)
# Things in [square brackets] or {curly braces} are treated as notes, not narration.
NOTE_RE = re.compile(r"\[[^\]]*\]|\{[^}]*\}")
MD_RE = re.compile(r"(\*\*|__|`|^#+\s*|^>\s*)", re.MULTILINE)
# Scene effect markers, placed right before the word that triggers them: [PIN], [PIN: Rome], [TEXT: 1940]
EFFECT_RE = re.compile(r"\[\s*(PIN|TEXT)\s*(?::\s*([^\]]*?))?\s*\]", re.IGNORECASE)
_SENTINEL_RE = re.compile("\x01(\\d+)\x01")


def read_script_file(path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".docx":
        import docx
        doc = docx.Document(str(path))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    lines.append(cell.text)
        return "\n".join(lines)
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def clean_narration(text: str) -> str:
    text = NOTE_RE.sub(" ", text)
    text = MD_RE.sub("", text)
    text = text.replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_effects(raw: str, scene_number=None):
    """Remove [PIN] / [TEXT: ...] markers from a scene's narration.

    Returns (clean narration, effects, warnings). Each effect is {"type": "pin"|"text", "text": str,
    "word": n} where n is the index of the spoken word that follows the marker (counted exactly like the
    sync does, so the effect lands on that word's measured time).
    """
    from .align import norm_tokens
    found, warnings = [], []
    where = f"Scene {scene_number}: " if scene_number is not None else ""

    def sub(m):
        kind, val = m.group(1).lower(), (m.group(2) or "").strip()
        if kind == "text" and not val:
            warnings.append(f"{where}[TEXT] needs words, like [TEXT: 1940] - it was ignored.")
            return " "
        found.append({"type": kind, "text": val})
        return f" \x01{len(found) - 1}\x01 "

    cleaned = clean_narration(EFFECT_RE.sub(sub, raw))
    words, effects, count = [], [], 0
    for tok in cleaned.split(" "):
        m = _SENTINEL_RE.fullmatch(tok)
        if m:
            e = dict(found[int(m.group(1))])
            e["word"] = count
            effects.append(e)
            continue
        if not tok:
            continue
        words.append(tok)
        if norm_tokens(tok):  # punctuation-only tokens are glued to the previous word, not counted
            count += 1
    for e in effects:
        if e["word"] >= count:
            warnings.append(f"{where}a [{e['type'].upper()}] marker has no word after it - it will appear on "
                            "the scene's last word.")
            e["word"] = max(0, count - 1)
    return " ".join(words), effects, warnings


def parse_scenes(text: str):
    """Return (scenes, warnings). Each scene = {"number": int, "text": str}."""
    warnings = []
    scenes = []
    current = None
    preamble = []
    for line in text.splitlines():
        m = SCENE_RE.match(line)
        if m:
            if current is not None:
                scenes.append(current)
            current = {"number": int(m.group(1)), "lines": [m.group(2)]}
        elif current is not None:
            current["lines"].append(line)
        elif line.strip():
            preamble.append(line.strip())
    if current is not None:
        scenes.append(current)

    out = []
    for s in scenes:
        narration, effects, fx_warn = extract_effects("\n".join(s["lines"]), s["number"])
        warnings.extend(fx_warn)
        sc = {"number": s["number"], "text": narration}
        if effects:
            sc["effects"] = effects
        out.append(sc)

    if not out:
        warnings.append('No scenes found. Each scene must start with a label like "Scene 1:" on its own line.')
        return out, warnings
    if preamble:
        warnings.append(f"Text before 'Scene {out[0]['number']}' was ignored: \"{' '.join(preamble)[:80]}...\"")
    nums = [s["number"] for s in out]
    seen, dups = set(), []
    for n in nums:
        if n in seen:
            dups.append(n)
        seen.add(n)
    if dups:
        warnings.append(f"Scene numbers used more than once: {sorted(set(dups))}")
    expected = list(range(nums[0], nums[0] + len(nums)))
    if nums != expected and not dups:
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            warnings.append(f"Scene numbers missing from the script: {missing[:20]}")
        if nums != sorted(nums):
            warnings.append("Scene numbers are not in order in the script. They are used in the order written.")
    empty = [s["number"] for s in out if not s["text"]]
    if empty:
        warnings.append(f"These scenes have no narration text: {empty}")
    return out, warnings


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]
