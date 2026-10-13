"""Align the whole script against the transcript (one long sequence) and find scene starts.

Every timing comes from the transcript's word timestamps (measured from the audio).
The algorithm is fully deterministic: the same inputs always give the same output.
"""
import difflib
import re
import unicodedata

from rapidfuzz.distance import Levenshtein

WORD_SPLIT = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")

NUMBER_WORDS = {"%": " percent ", "&": " and ", "+": " plus "}

# How many opening words of a scene we look at to judge confidence.
OPENING = 5
MIN_GAP = 0.25  # seconds; scenes closer than this are suspicious


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'").replace("'", "")
    for k, v in NUMBER_WORDS.items():
        s = s.replace(k, v)
    return s


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _say_under_100(n):
    if n < 20:
        return [_ONES[n]]
    return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])


def _say_under_1000(n):
    out = []
    if n >= 100:
        out += [_ONES[n // 100], "hundred"]
        n %= 100
        if n == 0:
            return out
    return out + _say_under_100(n)


def number_words(digits: str):
    """'1922' -> nineteen twenty two (year style); '250' -> two hundred fifty; '3000000' -> three million."""
    n = int(digits)
    if len(digits) > 1 and digits.startswith("0") or n > 999_999_999:
        return [_ONES[int(d)] for d in digits]
    if 1100 <= n <= 1999 or (2010 <= n <= 2099):
        hi, lo = divmod(n, 100)
        return _say_under_100(hi) + (["hundred"] if lo == 0 else (["oh"] + _say_under_100(lo) if lo < 10 else _say_under_100(lo)))
    if n == 0:
        return ["zero"]
    out = []
    for value, name in ((1_000_000, "million"), (1000, "thousand")):
        if n >= value:
            out += _say_under_1000(n // value) + [name]
            n %= value
    if n:
        out += _say_under_1000(n)
    return out


def norm_tokens(word: str):
    """'Well-known,' -> ['well', 'known'];  "Don't" -> ['dont'];  '1922' -> ['nineteen', 'twenty', 'two']"""
    text = _norm_text(word)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)  # 1,000 -> 1000
    out = []
    for tok in TOKEN_RE.findall(text):
        if tok.isdigit():
            out += number_words(tok)
        else:
            m = re.fullmatch(r"(\d+)(st|nd|rd|th|s)", tok)
            out += number_words(m.group(1)) if m else [tok]
    return out


def script_words(scenes):
    """Split each scene into display words (keeping the script's spelling and punctuation).

    Returns (words, tokens). words[i] = {"text", "scene"}; tokens[k] = {"key", "word"}.
    """
    words, tokens = [], []
    for si, sc in enumerate(scenes):
        for raw in WORD_SPLIT.split(sc["text"].strip()):
            if not raw:
                continue
            keys = norm_tokens(raw)
            if not keys:
                # Pure punctuation such as "-" : glue it to the previous word of the same scene.
                if words and words[-1]["scene"] == si:
                    words[-1]["text"] += " " + raw
                continue
            words.append({"text": raw, "scene": si})
            for k in keys:
                tokens.append({"key": k, "word": len(words) - 1})
    return words, tokens


def transcript_tokens(twords):
    """Expand transcript words into normalized tokens, sharing out each word's time span."""
    toks = []
    for w in twords:
        keys = norm_tokens(w["w"])
        if not keys:
            continue
        s, e = float(w["s"]), float(w["e"])
        n = len(keys)
        for i, k in enumerate(keys):
            toks.append({"key": k, "s": s + (e - s) * i / n, "e": s + (e - s) * (i + 1) / n})
    return toks


def _similar(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return Levenshtein.normalized_similarity(a, b)


def _dp_align(A, B, a0, a1, b0, b1, out):
    """Needleman-Wunsch with fuzzy word similarity on A[a0:a1] vs B[b0:b1]."""
    n, m = a1 - a0, b1 - b0
    if n == 0 or m == 0:
        return
    GAP = -0.6
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    move = [[0] * (m + 1) for _ in range(n + 1)]  # 1 diag, 2 up (skip A), 3 left (skip B)
    for i in range(1, n + 1):
        score[i][0] = i * GAP
        move[i][0] = 2
    for j in range(1, m + 1):
        score[0][j] = j * GAP
        move[0][j] = 3
    for i in range(1, n + 1):
        ai = A[a0 + i - 1]
        row, prev = score[i], score[i - 1]
        mrow = move[i]
        for j in range(1, m + 1):
            sim = _similar(ai, B[b0 + j - 1])
            sub = 2.0 if sim == 1.0 else (2.0 * sim - 0.4 if sim >= 0.6 else -1.0)
            d = prev[j - 1] + sub
            u = prev[j] + GAP
            l = row[j - 1] + GAP
            if d >= u and d >= l:
                row[j], mrow[j] = d, 1
            elif u >= l:
                row[j], mrow[j] = u, 2
            else:
                row[j], mrow[j] = l, 3
    i, j = n, m
    while i > 0 and j > 0:
        mv = move[i][j]
        if mv == 1:
            sim = _similar(A[a0 + i - 1], B[b0 + j - 1])
            if sim >= 0.6:
                out[a0 + i - 1] = (b0 + j - 1, sim)
            i, j = i - 1, j - 1
        elif mv == 2:
            i -= 1
        else:
            j -= 1


MAX_DP_CELLS = 1_500_000


def _align_region(A, B, a0, a1, b0, b1, out, min_block):
    """Exact-match anchors first, then fuzzy DP in the gaps between anchors."""
    if a0 >= a1 or b0 >= b1:
        return
    if (a1 - a0) * (b1 - b0) <= MAX_DP_CELLS and min_block <= 3:
        _dp_align(A, B, a0, a1, b0, b1, out)
        return
    sm = difflib.SequenceMatcher(None, A[a0:a1], B[b0:b1], autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= min_block]
    pa, pb = a0, b0
    for blk in blocks:
        ba, bb = a0 + blk.a, b0 + blk.b
        _align_region(A, B, pa, ba, pb, bb, out, max(2, min_block - 1))
        for k in range(blk.size):
            out[ba + k] = (bb + k, 1.0)
        pa, pb = ba + blk.size, bb + blk.size
    if blocks:
        _align_region(A, B, pa, a1, pb, b1, out, max(2, min_block - 1))
    elif (a1 - a0) * (b1 - b0) <= MAX_DP_CELLS * 4:
        _dp_align(A, B, a0, a1, b0, b1, out)


def align_tokens(stoks, ttoks):
    """Return list (len = script tokens) of (transcript_index, similarity) or None."""
    A = [t["key"] for t in stoks]
    B = [t["key"] for t in ttoks]
    out = [None] * len(A)
    _align_region(A, B, 0, len(A), 0, len(B), out, min_block=4)
    # Safety: enforce strictly increasing transcript indices.
    last = -1
    for i, m in enumerate(out):
        if m is not None:
            if m[0] <= last:
                out[i] = None
            else:
                last = m[0]
    return out


def sync(scenes, twords, audio_duration, lead_in=0.0):
    """Main entry. Returns dict with per-scene results and per-word timings.

    scenes: [{"number", "text"}]; twords: [{"w","s","e"}] from the transcript.
    """
    words, stoks = script_words(scenes)
    ttoks = transcript_tokens(twords)
    match = align_tokens(stoks, ttoks)
    matched_t = set(m[0] for m in match if m is not None)

    # ---- scene starts -------------------------------------------------------
    scene_tok_ranges = []
    k = 0
    for si in range(len(scenes)):
        start = k
        while k < len(stoks) and words[stoks[k]["word"]]["scene"] == si:
            k += 1
        scene_tok_ranges.append((start, k))

    results = []
    prev_t_idx = -1  # last transcript token index used by earlier script tokens
    for si, sc in enumerate(scenes):
        a, b = scene_tok_ranges[si]
        res = {"number": sc["number"], "start": None, "confidence": 0.0, "flag": "", "method": ""}
        if a == b:
            res["flag"] = "Scene has no narration words"
        else:
            opening = list(range(a, min(b, a + OPENING)))
            good = [i for i in opening if match[i] is not None]
            res["confidence"] = round(len(good) / len(opening), 2)
            first = next((i for i in range(a, min(b, a + 3 * OPENING)) if match[i] is not None), None)
            if first is None:
                res["flag"] = "Opening words not found in the voiceover"
            else:
                tj = match[first][0]
                d = first - a  # how many leading script tokens were not matched
                if d == 0:
                    # A word heard as two ("nobody" -> "no body"): the opening may begin one token earlier.
                    if (match[first][1] < 1.0 and tj - 1 > prev_t_idx and (tj - 1) not in matched_t and
                            _similar(stoks[first]["key"], ttoks[tj - 1]["key"] + ttoks[tj]["key"]) > match[first][1]):
                        tj -= 1
                    res["start"] = ttoks[tj]["s"]
                    res["method"] = "exact" if match[first][1] == 1.0 else "fuzzy"
                else:
                    # The first words may have been mis-heard. If there are unmatched transcript words just
                    # before the first matched one, they are almost certainly those words: use their start.
                    back = tj
                    while back - 1 > prev_t_idx and (back - 1) not in matched_t and tj - (back - 1) <= d:
                        back -= 1
                    res["start"] = ttoks[back]["s"]
                    res["method"] = "recovered" if back < tj else "later word"
                if res["confidence"] < 0.6:
                    res["flag"] = "Low confidence - only {}/{} opening words matched".format(len(good), len(opening))
        for i in range(a, b):
            if match[i] is not None:
                prev_t_idx = max(prev_t_idx, match[i][0])
        results.append(res)

    # ---- order checks and estimates for scenes that could not be found -------
    for i, r in enumerate(results):
        if r["start"] is None:
            continue
        prev = next((results[j]["start"] for j in range(i - 1, -1, -1) if results[j]["start"] is not None), None)
        if prev is not None and r["start"] < prev + MIN_GAP:
            r["flag"] = r["flag"] or "Start time is out of order / too close to previous scene"
            r["start"] = None

    _fill_estimates(results, scene_tok_ranges, audio_duration)

    if lead_in:
        for i, r in enumerate(results):
            if i > 0:
                r["start"] = max(0.0, r["start"] - lead_in)

    # ---- word timings for captions (script spelling, audio timing) -----------
    word_times = _word_times(words, stoks, ttoks, match, audio_duration)

    total = len(stoks)
    matched = sum(1 for m in match if m is not None)
    return {
        "scenes": results,
        "words": [{"text": w["text"], "scene": w["scene"], "s": round(t[0], 3), "e": round(t[1], 3)}
                  for w, t in zip(words, word_times)],
        "match_rate": round(matched / total, 3) if total else 0.0,
    }


def _fill_estimates(results, tok_ranges, audio_duration):
    """Scenes whose start was not found get an estimate (by word count) and keep their FLAG."""
    n = len(results)
    for i, r in enumerate(results):
        if r["start"] is not None:
            r["start"] = round(float(r["start"]), 3)
            r["estimated"] = False
            continue
        r["estimated"] = True
        if not r["flag"]:
            r["flag"] = "Start could not be found"
        r["flag"] += " - ESTIMATED, please check"
        # previous known anchor
        pi = next((j for j in range(i - 1, -1, -1) if results[j]["start"] is not None and not results[j].get("estimated")), None)
        ni = next((j for j in range(i + 1, n) if results[j]["start"] is not None), None)
        t0 = results[pi]["start"] if pi is not None else 0.0
        w0 = tok_ranges[pi][0] if pi is not None else 0
        t1 = results[ni]["start"] if ni is not None else audio_duration
        w1 = tok_ranges[ni][0] if ni is not None else (tok_ranges[-1][1] if tok_ranges else 1)
        wi = tok_ranges[i][0]
        frac = (wi - w0) / (w1 - w0) if w1 > w0 else 0.5
        r["start"] = round(t0 + (t1 - t0) * frac, 3)
    if results:
        results[0]["start"] = results[0]["start"] if results[0]["start"] is not None else 0.0


def _word_times(words, stoks, ttoks, match, audio_duration):
    """Per display word (start, end). Unmatched words are spread between matched neighbours."""
    nw = len(words)
    ws = [None] * nw
    we = [None] * nw
    for ti, m in enumerate(match):
        if m is None:
            continue
        wi = stoks[ti]["word"]
        t = ttoks[m[0]]
        ws[wi] = t["s"] if ws[wi] is None else min(ws[wi], t["s"])
        we[wi] = t["e"] if we[wi] is None else max(we[wi], t["e"])
    i = 0
    while i < nw:
        if ws[i] is not None:
            i += 1
            continue
        j = i
        while j < nw and ws[j] is None:
            j += 1
        left = we[i - 1] if i > 0 else 0.0
        right = ws[j] if j < nw else min(audio_duration, left + 0.35 * (j - i) + 0.2)
        right = max(right, left)
        lens = [max(1, len(words[k]["text"])) for k in range(i, j)]
        tot = sum(lens)
        t = left
        for k, L in zip(range(i, j), lens):
            span = (right - left) * L / tot
            ws[k], we[k] = t, t + span
            t += span
        i = j
    return list(zip(ws, we))
