from pathlib import Path

from channels.video.timeline import Clip, Scene, Subtitle, Timeline

TL = Timeline(1920, 1080, (
    Scene(1, "저녁 식탁", Path("img/01.png"), Path("music/잔잔.mp3"), 3.5,
          (Clip(Path("w/001_000.mp3"), 0.0), Clip(Path("w/001_001.mp3"), 1.9)),
          (Subtitle("그날 저녁,", "#FFFFFF", 0.0, 1.5), Subtitle("너희 올 거니?", "#FFD400", 1.9, 2.5))),
    Scene(2, "다음 날", Path("img/02.png"), None, 2.0,
          (Clip(Path("w/002_000.mp3"), 0.0),), (Subtitle("아침이 밝았다.", "#FFFFFF", 0.0, 1.0),)),
))


def test_starts_and_total():
    assert TL.starts() == [0.0, 3.5] and TL.total == 5.5 and TL.size == (1920, 1080)


def test_json_roundtrip():
    assert Timeline.from_json(TL.to_json()) == TL


def test_srt_uses_absolute_times():
    assert TL.to_srt() == (
        "1\n00:00:00,000 --> 00:00:01,500\n그날 저녁,\n\n"
        "2\n00:00:01,900 --> 00:00:02,500\n너희 올 거니?\n\n"
        "3\n00:00:03,500 --> 00:00:04,500\n아침이 밝았다.\n"
    )
