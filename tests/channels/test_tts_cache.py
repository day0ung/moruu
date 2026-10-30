from channels.tts.cache import CachedTTS
from channels.tts.google import Part, Speech, Word


class Inner:
    def __init__(self):
        self.calls = []

    def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
        self.calls.append((tuple(parts), voice, rate, pitch))
        return Speech(f"MP3-{len(self.calls)}".encode(), [Word(p.text, 0.5 * i) for i, p in enumerate(parts)], 1.5)


def test_same_input_hits_cache(tmp_path):
    inner = Inner()
    tts = CachedTTS(inner, tmp_path)
    a = tts.synthesize_parts([Part("가", 0.5), Part("나")], "V", 0.9, -2.0)
    b = CachedTTS(inner, tmp_path).synthesize_parts([Part("가", 0.5), Part("나")], "V", 0.9, -2.0)
    assert len(inner.calls) == 1
    assert b == a == Speech(b"MP3-1", [Word("가", 0.0), Word("나", 0.5)], 1.5)


def test_any_change_misses_cache(tmp_path):
    inner = Inner()
    tts = CachedTTS(inner, tmp_path)
    base = ([Part("가", 0.5)], "V", 1.0, 0.0)
    tts.synthesize_parts(*base)
    tts.synthesize_parts([Part("가", 0.6)], "V", 1.0, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "W", 1.0, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "V", 1.1, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "V", 1.0, 1.0)
    CachedTTS(inner, tmp_path, provider="typecast").synthesize_parts(*base)
    assert len(inner.calls) == 6


def test_missing_end_roundtrips_as_none(tmp_path):
    class NoEnd(Inner):
        def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
            super().synthesize_parts(parts, voice, rate, pitch)
            return Speech(b"X", [], None)

    inner = NoEnd()
    CachedTTS(inner, tmp_path).synthesize_parts([Part("가")], "V")
    assert CachedTTS(inner, tmp_path).synthesize_parts([Part("가")], "V") == Speech(b"X", [], None)
    assert len(inner.calls) == 1
