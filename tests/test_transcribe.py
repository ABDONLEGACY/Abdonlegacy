"""The transcribe step must hand faster-whisper decoded audio (not a file path), so faster-whisper never
opens files with PyAV (PyAV 19 broke that: "unexpected keyword argument 'metadata_errors'")."""
import os
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("SCENEFORGE_TEST_TRANSCRIPT", None)

from sceneforge import ffmpeg_utils as ff, transcribe  # noqa: E402


def test_transcribe_passes_array():
    tmp = Path(tempfile.mkdtemp())
    wav = tmp / "v.wav"
    ff.run(["-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-ac", "2", "-ar", "44100", str(wav)])
    seen = {}

    class FakeModel:
        def transcribe(self, audio, **kw):
            seen["audio"] = audio
            w = types.SimpleNamespace(word=" hello", start=0.5, end=0.9, probability=0.9)
            seg = types.SimpleNamespace(words=[w], end=3.0)
            return iter([seg]), types.SimpleNamespace(duration=3.0)

    transcribe.load_model = lambda size="small": FakeModel()
    words = transcribe.transcribe(wav, tmp, "small", "en", duration=3.0)
    a = seen["audio"]
    assert isinstance(a, np.ndarray) and a.dtype == np.float32 and a.ndim == 1, type(a)
    assert abs(len(a) - 48000) < 200, len(a)  # 3 s at 16 kHz mono
    assert words == [{"w": " hello", "s": 0.5, "e": 0.9, "p": 0.9}]
    # cached second time
    assert transcribe.transcribe(wav, tmp, "small", "en") == words


def test_faster_whisper_accepts_array():
    """faster-whisper's own audio front end (feature extractor + VAD) works on our array without PyAV."""
    from faster_whisper.feature_extractor import FeatureExtractor
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    audio = np.zeros(16000 * 2, np.float32)
    feats = FeatureExtractor(feature_size=80)(audio)
    assert feats.shape[0] == 80
    get_speech_timestamps(audio, VadOptions())


if __name__ == "__main__":
    test_transcribe_passes_array()
    test_faster_whisper_accepts_array()
    print("TRANSCRIBE TESTS PASSED")
