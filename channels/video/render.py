"""Timeline → mp4 + srt. 장면마다 조각을 만들고(내용이 같으면 재사용) 이어 붙인 뒤 음악을 깐다."""
from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from channels.video.ffmpeg import MusicSpan, Overlay, VideoError, concat, mix_args, run, scene_args
from channels.video.frames import cover_png, hex_rgb, subtitle_png
from channels.video.timeline import Scene, Timeline

FADE = 0.3  # 장면 앞뒤 어두워졌다 밝아짐(초)
SUB_SIZE = 56  # 가로 화면 자막 글자 크기
VERSION = "1"  # 장면 조각 모양을 바꾸면 올린다 — 캐시 무효화

log = logging.getLogger("moruu")


def scene_key(scene: Scene, size: tuple[int, int]) -> str:
    h = hashlib.sha256()
    h.update(f"{VERSION}|{size}|{scene.duration:.3f}|{FADE}|{SUB_SIZE}".encode())
    h.update(scene.image.read_bytes() if scene.image.is_file() else str(scene.image).encode())
    for c in scene.clips:
        h.update(f"|{c.start:.3f}|".encode())
        h.update(c.audio.read_bytes() if c.audio.is_file() else str(c.audio).encode())
    for s in scene.subtitles:
        h.update(f"|{s.text}|{s.color}|{s.start:.3f}|{s.stop:.3f}".encode())
    return h.hexdigest()


def music_spans(timeline: Timeline) -> list[MusicSpan]:
    """같은 곡이 이어지는 장면을 한 구간으로. 음악 없는 장면(첫 태그 전)은 건너뛴다."""
    spans: list[MusicSpan] = []
    for start, s in zip(timeline.starts(), timeline.scenes):
        if s.music is None:
            continue
        if spans and spans[-1].path == s.music and abs(spans[-1].start + spans[-1].duration - start) < 1e-6:
            last = spans.pop()
            spans.append(MusicSpan(last.path, last.start, last.duration + s.duration))
        else:
            spans.append(MusicSpan(s.music, start, s.duration))
    return spans


def _scene(s: Scene, size: tuple[int, int], work: Path, font: Path) -> Path:
    stem = f"scene{s.number:03}"
    seg = work / f"{stem}_{scene_key(s, size)[:16]}.mp4"
    if seg.is_file():
        return seg
    bg = cover_png(s.image.read_bytes(), work / f"{stem}_bg.png", canvas=size)
    overlays = [
        Overlay(subtitle_png(x.text, work / f"{stem}_sub{i}.png", font, center_y=size[1] - 120, size=SUB_SIZE,
                             color=hex_rgb(x.color), canvas=size), x.start, x.stop)
        for i, x in enumerate(s.subtitles)
    ]
    tmp = seg.with_name(seg.stem + "_tmp.mp4")
    try:
        run(scene_args(tmp, bg, [(c.audio, c.start) for c in s.clips], s.duration, overlays, size, FADE))
    except VideoError as e:
        raise VideoError(f"장면 {s.number}: {e}") from e
    tmp.replace(seg)  # 다 만들어진 뒤에만 캐시로 친다
    return seg


def render(timeline: Timeline, work: Path, out: Path, font: Path, *,
           music_db: float = -18.0, xfade: float = 2.0) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    segments = []
    for s in timeline.scenes:
        segments.append(_scene(s, timeline.size, work, font))
        log.info("장면 %d 완료", s.number)
    joined = concat(segments, work / "joined.mp4")
    spans = music_spans(timeline)
    if spans:
        run(mix_args(joined, spans, out, music_db, xfade))
    else:
        shutil.copyfile(joined, out)
    out.with_suffix(".srt").write_text(timeline.to_srt(), encoding="utf-8")
    return out
