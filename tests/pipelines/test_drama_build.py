import pytest

from channels.tts.google import Speech, Word
from channels.video.timeline import Clip, Subtitle
from pipelines.ai_drama.bible import Character
from pipelines.ai_drama.build import build_timeline
from pipelines.ai_drama.script import DramaScene, Spoken

CAST = {"내레이션": Character("내레이션", "N", 0.0, 1.0, "#FFFFFF"),
        "시어머니": Character("시어머니", "M", -4.0, 0.9, "#FFD400")}
LONG = "그날 저녁, 시어머니는 아무 말 없이 조용히 상을 차렸다."


class FakeTTS:
    """조각마다 0.5초, 끝 = 조각 수 × 0.5."""

    def __init__(self):
        self.calls = []

    def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
        self.calls.append((" ".join(p.text for p in parts), voice, rate, pitch))
        return Speech(b"MP3", [Word(p.text, 0.5 * i) for i, p in enumerate(parts)], 0.5 * len(parts))


def test_times_colors_voices(tmp_path):
    scenes = [
        DramaScene(1, "저녁", "잔잔", [Spoken("내레이션", "", LONG), Spoken("시어머니", "서운하게", "너희 올 거니?")],
                   tmp_path / "01.png", "AI"),
        DramaScene(2, "아침", None, [Spoken("내레이션", "", "{3M|쓰리엠} 아침")], tmp_path / "02.png", "AI"),
    ]
    tts = FakeTTS()
    tl = build_timeline(scenes, CAST, tts, {}, tmp_path / "w", {"잔잔": tmp_path / "잔잔.mp3"})

    assert tts.calls == [(LONG, "N", 1.0, 0.0), ("너희 올 거니?", "M", 0.9, -4.0), ("쓰리엠 아침", "N", 1.0, 0.0)]
    s1, s2 = tl.scenes
    # 내레이션 24자 초과 → 자막 두 줄(조각 2개, 1.0초), 다음 줄은 1.0 + 0.4 에 시작
    assert s1.clips == (Clip(tmp_path / "w" / "001_000.mp3", 0.0), Clip(tmp_path / "w" / "001_001.mp3", 1.4))
    assert [x.color for x in s1.subtitles] == ["#FFFFFF", "#FFFFFF", "#FFD400"]
    assert s1.subtitles[-1] == Subtitle("너희 올 거니?", "#FFD400", 1.4, 1.9)
    assert s1.duration == pytest.approx(1.9 + 1.0)
    assert (s1.music, s2.music) == (tmp_path / "잔잔.mp3", None)
    assert s2.subtitles == (Subtitle("3M 아침", "#FFFFFF", 0.0, 0.5),)
    assert (tl.width, tl.height) == (1920, 1080)
    assert (tmp_path / "w" / "002_000.mp3").read_bytes() == b"MP3"
