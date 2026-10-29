"""장면 목록 → mp4. 장면마다 TTS → 배경·글자 PNG → 세그먼트, 마지막에 마무리 카드를 붙여 이어 붙인다."""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from channels.tts.google import Speech
from channels.tts.srt import cues
from channels.video.ffmpeg import Overlay, concat, make_segment, media_duration
from channels.video.frames import Span, caption_png, card_png, cover_png, subtitle_png
from pipelines.shopping_shorts.script import Scene

PAD = 0.4  # 내레이션 끝난 뒤 장면을 더 보여 줄 시간(초)
ENDING = Scene(99, "카드", [Span("제품 정보는 "), Span("프로필 링크", True), Span("에서")],
               "제품 정보는 프로필 링크에서 확인하세요.")
ENDING_NOTE = "제품 모양·크기는 상품 페이지에서 확인하세요"

log = logging.getLogger("moruu")


class TTS(Protocol):
    def synthesize(self, text: str, voice: str, rate: float = 1.0) -> Speech: ...


def render_short(scenes: list[Scene], disclosure: str, *, tts: TTS, fetch: Callable[[str], bytes],
                 work: Path, out: Path, font: Path, voice: str, rate: float) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    segments = []
    for s in [*scenes, ENDING]:
        notes = [ENDING_NOTE, disclosure] if s is ENDING else []
        segments.append(_segment(s, notes, tts, fetch, work, font, voice, rate))
        log.info("장면 %s 완료", "마무리" if s is ENDING else s.number)
    return concat(segments, out)


def _segment(s: Scene, notes: list[str], tts: TTS, fetch: Callable[[str], bytes],
             work: Path, font: Path, voice: str, rate: float) -> Path:
    stem = work / f"{s.number:02}"
    speech = tts.synthesize(s.narration, voice, rate)
    audio = stem.with_suffix(".mp3")
    audio.write_bytes(speech.audio)
    spoken = speech.end if speech.end is not None else media_duration(audio)
    duration = spoken + PAD

    if s.kind == "이미지":
        background = cover_png(fetch(s.image_url), stem.with_name(f"{stem.name}_bg.png"))
        caption_y, zoom = 300, True
    else:
        background = card_png(stem.with_name(f"{stem.name}_bg.png"), font, notes)
        caption_y, zoom = 760, False

    overlays = []
    if s.caption:
        overlays.append(Overlay(caption_png(s.caption, stem.with_name(f"{stem.name}_cap.png"), font, center_y=caption_y)))
    timed = cues(speech.words, speech.end)
    if not timed:  # 단어 시각이 없는 목소리 — 내레이션 전체를 한 번에
        overlays.append(Overlay(subtitle_png(s.narration, stem.with_name(f"{stem.name}_sub0.png"), font), 0.0, spoken))
    for i, c in enumerate(timed):
        png = subtitle_png(c.text, stem.with_name(f"{stem.name}_sub{i}.png"), font)
        overlays.append(Overlay(png, c.start, c.stop))

    return make_segment(stem.with_suffix(".mp4"), background, audio, duration, overlays, zoom)
