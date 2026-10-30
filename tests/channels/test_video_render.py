from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from channels.video import render as R
from channels.video.ffmpeg import MusicSpan, media_duration, run
from channels.video.frames import FontError, find_font
from channels.video.timeline import Clip, Scene, Subtitle, Timeline

try:
    FONT = find_font({})
except FontError:
    FONT = None


def scene(n, music, duration=2.0, image=Path("i.png")):
    return Scene(n, f"장면{n}", image, music, duration, (Clip(Path("a.mp3"), 0.0),), ())


def test_music_spans_group_same_track_and_skip_leading_silence():
    a, b = Path("a.mp3"), Path("b.mp3")
    tl = Timeline(1920, 1080, (scene(1, None), scene(2, a), scene(3, a, 3.0), scene(4, b)))
    assert R.music_spans(tl) == [MusicSpan(a, 2.0, 5.0), MusicSpan(b, 7.0, 2.0)]
    assert R.music_spans(Timeline(1920, 1080, (scene(1, None),))) == []


def test_scene_key_changes_with_image_content(tmp_path):
    img, audio = tmp_path / "i.png", tmp_path / "a.mp3"
    img.write_bytes(b"one")
    audio.write_bytes(b"sound")
    s = Scene(1, "t", img, None, 2.0, (Clip(audio, 0.0),), (Subtitle("가", "#FFFFFF", 0, 1),))
    k1 = R.scene_key(s, (1920, 1080))
    assert R.scene_key(s, (1920, 1080)) == k1
    img.write_bytes(b"two")
    assert R.scene_key(s, (1920, 1080)) != k1
    assert R.scene_key(replace(s, duration=2.5), (1920, 1080)) != R.scene_key(s, (1920, 1080))


def silent(path, seconds):
    run(["-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds), "-c:a", "libmp3lame", str(path)])
    return path


def tone(path, seconds):
    run(["-y", "-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}", "-c:a", "libmp3lame", str(path)])
    return path


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_render_two_scenes_with_music_and_reuses_segments(tmp_path):
    img = tmp_path / "01.png"
    Image.new("RGB", (640, 360), (120, 140, 160)).save(img)
    a = silent(tmp_path / "a.mp3", 0.6)
    music = tone(tmp_path / "m.mp3", 1.0)  # 장면보다 짧음 — 반복돼야 함
    subs = (Subtitle("그날 저녁,", "#FFD400", 0.0, 0.6),)
    tl = Timeline(1920, 1080, (
        Scene(1, "하나", img, music, 1.5, (Clip(a, 0.0), Clip(a, 0.7)), subs),
        Scene(2, "둘", img, music, 1.2, (Clip(a, 0.0),), ()),
    ))
    out = R.render(tl, tmp_path / "work", tmp_path / "ep.mp4", FONT)
    assert media_duration(out) == pytest.approx(2.7, abs=0.2)
    assert out.with_suffix(".srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000 --> 00:00:00,600\n그날 저녁,")

    made = sorted(p.name for p in (tmp_path / "work").glob("scene*.mp4"))
    assert len(made) == 2
    stamp = [(tmp_path / "work" / n).stat().st_mtime_ns for n in made]
    R.render(tl, tmp_path / "work", tmp_path / "ep.mp4", FONT)
    assert [(tmp_path / "work" / n).stat().st_mtime_ns for n in made] == stamp  # 다시 안 만듦

    changed = Timeline(1920, 1080, (replace(tl.scenes[0], duration=1.6), tl.scenes[1]))
    R.render(changed, tmp_path / "work", tmp_path / "ep.mp4", FONT)
    after = sorted(p.name for p in (tmp_path / "work").glob("scene*.mp4"))
    assert len(after) == 2 and after[1] == made[1] and after[0] != made[0]  # 바뀐 장면의 옛 조각은 지움
