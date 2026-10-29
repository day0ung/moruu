from pathlib import Path

import pytest
from PIL import Image

from channels.video.ffmpeg import (
    Overlay, VideoError, concat, concat_args, make_segment, media_duration, run, segment_args,
)
from channels.video.frames import H, W


def test_segment_args_chains_overlays_with_timing():
    args = segment_args(Path("seg.mp4"), Path("bg.png"), Path("a.mp3"), 2.5,
                        [Overlay(Path("cap.png")), Overlay(Path("sub.png"), 0.0, 1.2)], zoom=True)
    graph = args[args.index("-filter_complex") + 1]
    assert "zoompan=z='1+0.08*on/75'" in graph
    assert "[v0][2:v]overlay=0:0[v1]" in graph
    assert "[v1][3:v]overlay=0:0:enable='between(t,0.000,1.200)'[v2]" in graph
    assert args[args.index("-map") + 1] == "[v2]"
    assert args[-1] == "seg.mp4" and "2.500" in args


def test_card_segment_has_no_zoom():
    args = segment_args(Path("s.mp4"), Path("bg.png"), Path("a.mp3"), 1.0, [], zoom=False)
    assert "zoompan" not in args[args.index("-filter_complex") + 1]


def test_concat_args_copy_streams():
    args = concat_args(Path("l.txt"), Path("o.mp4"))
    assert args[:7] == ["-y", "-f", "concat", "-safe", "0", "-i", "l.txt"]
    assert args[-5:] == ["-c", "copy", "-movflags", "+faststart", "o.mp4"]


def test_run_error_has_reason():
    with pytest.raises(VideoError):
        run(["-i", "없는파일.png", "out.mp4"])


def silent_mp3(path: Path, seconds: float) -> Path:
    run(["-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds), "-c:a", "libmp3lame", str(path)])
    return path


def test_real_render_two_segments_and_concat(tmp_path):
    bg = tmp_path / "bg.png"
    Image.new("RGB", (W, H), (200, 230, 220)).save(bg)
    over = tmp_path / "o.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(over)
    audio = silent_mp3(tmp_path / "a.mp3", 0.5)
    s1 = make_segment(tmp_path / "1.mp4", bg, audio, 0.6, [Overlay(over, 0, 0.3)], zoom=True)
    s2 = make_segment(tmp_path / "2.mp4", bg, audio, 0.6, [Overlay(over)], zoom=False)
    out = concat([s1, s2], tmp_path / "final.mp4")
    assert media_duration(out) == pytest.approx(1.2, abs=0.15)
