from pathlib import Path

import pytest
from PIL import Image

from channels.video.ffmpeg import (
    MusicSpan, Overlay, VideoError, concat, concat_args, make_segment, media_duration, mix_args, run, scene_args,
    segment_args,
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


def test_scene_args_delays_each_clip_and_fades():
    args = scene_args(Path("s.mp4"), Path("bg.png"), [(Path("a.mp3"), 0.0), (Path("b.mp3"), 1.25)], 3.0,
                      [Overlay(Path("o.png"), 0.0, 1.0)], (1920, 1080), fade=0.3)
    graph = args[args.index("-filter_complex") + 1]
    assert args.count("-i") == 4  # 배경 + 음성 2 + 자막 1
    assert "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080" in graph
    assert "zoompan=" in graph and "s=1920x1080" in graph
    assert "[1:a]adelay=delays=0:all=1[c0]" in graph
    assert "[2:a]adelay=delays=1250:all=1[c1]" in graph
    assert "[c0][c1]amix=inputs=2:normalize=0,apad[a]" in graph
    assert "[v0][3:v]overlay=0:0:enable='between(t,0.000,1.000)'[v1]" in graph
    assert "fade=t=in:st=0:d=0.300,fade=t=out:st=2.700:d=0.300" in graph
    assert args[-1] == "s.mp4" and "-t" in args


def test_mix_args_crossfades_groups_and_ducks():
    args = mix_args(Path("v.mp4"), [MusicSpan(Path("calm.mp3"), 5.0, 30.0), MusicSpan(Path("sad.mp3"), 35.0, 20.0)],
                    Path("o.mp4"), music_db=-18, xfade=2.0)
    graph = args[args.index("-filter_complex") + 1]
    assert args[:5] == ["-y", "-i", "v.mp4", "-stream_loop", "-1"]
    assert "[1:a]atrim=0:32.000,asetpts=PTS-STARTPTS[m0]" in graph
    assert "[2:a]atrim=0:22.000,asetpts=PTS-STARTPTS[m1]" in graph
    assert "[m0][m1]acrossfade=d=2.000[x1]" in graph
    assert "[x1]adelay=delays=5000:all=1,volume=-18dB[mus]" in graph
    assert "sidechaincompress" in graph and "amix=inputs=2:normalize=0:duration=first[a]" in graph
    i = args.index("-map")
    assert args[i:i + 6] == ["-map", "0:v", "-map", "[a]", "-c:v", "copy"]


def test_mix_args_single_group_no_crossfade():
    args = mix_args(Path("v.mp4"), [MusicSpan(Path("calm.mp3"), 0.0, 10.0)], Path("o.mp4"))
    graph = args[args.index("-filter_complex") + 1]
    assert "acrossfade" not in graph and "[m0]adelay=delays=0:all=1,volume=-18dB[mus]" in graph


def test_real_scene_with_two_clips(tmp_path):
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1920, 1080), (200, 230, 220)).save(bg)
    a = silent_mp3(tmp_path / "a.mp3", 0.5)
    run(scene_args(tmp_path / "s.mp4", bg, [(a, 0.0), (a, 0.9)], 1.6, [], (1920, 1080)))
    assert media_duration(tmp_path / "s.mp4") == pytest.approx(1.6, abs=0.15)
