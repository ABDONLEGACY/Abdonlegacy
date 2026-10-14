"""Speech-to-text with word timestamps using faster-whisper on the CPU (int8).

Results are cached per (audio content, model, language) so the same inputs always give the same timings
and re-opening a project does not transcribe again.
"""
import hashlib
import json
import os
from pathlib import Path

from . import paths

MODEL_CHOICES = ["small", "medium", "base", "tiny"]


def file_hash(path, chunk=1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _local_model_dir(model_size: str):
    """Return the already-downloaded model folder, or None."""
    base = paths.MODELS_DIR / f"models--Systran--faster-whisper-{model_size}" / "snapshots"
    if base.is_dir():
        for snap in sorted(base.iterdir()):
            if (snap / "model.bin").exists():
                return str(snap)
    return None


def load_model(model_size="small"):
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from faster_whisper import WhisperModel
    local = _local_model_dir(model_size)
    threads = max(1, (os.cpu_count() or 4))
    if local:
        return WhisperModel(local, device="cpu", compute_type="int8", cpu_threads=threads)
    # First use of this model size: download it once (about 460 MB for "small", 1.5 GB for "medium").
    paths.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=threads,
                        download_root=str(paths.MODELS_DIR))


def load_audio_16k(path):
    """Audio file -> float32 numpy array, mono, 16 kHz."""
    from . import ffmpeg_utils as ff
    return ff.read_audio_f32(path, sr=16000, channels=1)[:, 0]


def transcribe(audio_path, cache_dir, model_size="small", language="en", duration=None, progress=None):
    """Return list of words: [{"w": " word", "s": start, "e": end, "p": probability}]."""
    test_words = os.environ.get("SCENEFORGE_TEST_TRANSCRIPT")  # automated tests only
    if test_words:
        return json.loads(Path(test_words).read_text(encoding="utf-8"))
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    lang = None if language in (None, "", "auto") else language
    key = f"{file_hash(audio_path)[:16]}_{model_size}_{lang or 'auto'}"
    cache = cache_dir / f"transcript_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["words"]

    if progress:
        progress(0.0, f"Loading speech model '{model_size}' ...")
    model = load_model(model_size)
    # Decode the audio ourselves with FFmpeg (16 kHz mono, what Whisper expects) instead of letting
    # faster-whisper open the file with PyAV: some PyAV versions reject faster-whisper's options
    # ("open() got an unexpected keyword argument 'metadata_errors'").
    audio = load_audio_16k(audio_path)
    segments, info = model.transcribe(
        audio,
        language=lang,
        beam_size=5,
        temperature=0.0,                  # no random fallback sampling -> deterministic
        condition_on_previous_text=False,  # avoids repeated-text loops on long audio
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    total = duration or getattr(info, "duration", None) or 1.0
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word, "s": round(float(w.start), 3), "e": round(float(w.end), 3),
                          "p": round(float(w.probability), 3)})
        if progress:
            progress(min(0.99, seg.end / total), f"Transcribing ... {seg.end/60:.1f} of {total/60:.1f} min")
    cache.write_text(json.dumps({"model": model_size, "language": lang, "words": words}, indent=0),
                     encoding="utf-8")
    return words
