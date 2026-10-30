"""컷 목록 → mp4. 컷마다 TTS → 배경·글자 PNG → 세그먼트, 마지막에 마무리 카드를 붙여 이어 붙인다."""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from channels.tts import narration
from channels.tts.google import Part, Speech
from channels.tts.srt import line_cues
from channels.video.ffmpeg import Overlay, concat, make_segment, media_duration
from channels.video.frames import Span, caption_png, card_png, cover_png, subtitle_png
from pipelines.shopping_shorts.script import Cut

PAD = 0.4  # 대사 끝난 뒤 컷을 더 보여 줄 시간(초)
LINE_MAX = 14  # 세로 화면 자막 한 줄 글자 수 (64px)
CAPTION_Y = 300  # 화면 문구는 상단
ENDING = Cut(99, [Span("제품 정보는 "), Span("프로필 링크", True), Span("에서")],
             ["제품 정보는 프로필 링크에서 확인하세요."])
ENDING_NOTE = "제품 모양·크기는 상품 페이지에서 확인하세요"

log = logging.getLogger("moruu")


class TTS(Protocol):
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0) -> Speech: ...


@dataclass(frozen=True)
class Voice:
    names: Mapping[str, str]  # {"여": 목소리 이름, "남": ...}
    default: str  # 컷에 태그가 없을 때 (페이지 `목소리`)
    rate: float

    def name(self, cut: Cut) -> str:
        return self.names[cut.voice or self.default]


def render_short(cuts: list[Cut], disclosure: str, *, tts: TTS, fetch: Callable[[str], bytes],
                 work: Path, out: Path, font: Path, voices: Mapping[str, str], default_voice: str,
                 rate: float, lexicon: Mapping[str, str]) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = Voice(voices, default_voice, rate)
    segments = []
    for c in [*cuts, ENDING]:
        notes = [ENDING_NOTE, disclosure] if c is ENDING else []
        segments.append(_segment(c, notes, tts, fetch, work, font, voice, lexicon))
        log.info("컷 %s 완료", "마무리" if c is ENDING else c.number)
    return concat(segments, out)


def _background(c: Cut, fetch: Callable[[str], bytes], path: Path, font: Path, notes: list[str]) -> Path:
    if c.image_url:
        return cover_png(fetch(c.image_url), path)
    if c.image_path:
        return cover_png(c.image_path.read_bytes(), path)
    return card_png(path, font, notes)


def _segment(c: Cut, notes: list[str], tts: TTS, fetch: Callable[[str], bytes],
             work: Path, font: Path, voice: Voice, lexicon: Mapping[str, str]) -> Path:
    stem = work / f"{c.number:02}"
    lines = [line for raw in c.lines for line in narration.to_lines(raw, lexicon, LINE_MAX)]
    speech = tts.synthesize_parts([p for line in lines for p in line.parts], voice.name(c), voice.rate)
    audio = stem.with_suffix(".mp3")
    audio.write_bytes(speech.audio)
    spoken = speech.end if speech.end is not None else media_duration(audio)
    duration = spoken + PAD
    if c.seconds is not None:
        if c.seconds < spoken:
            raise ValueError(f"컷 {c.number}: 대사가 {spoken:.1f}초라 #{c.seconds:g}초 안에 안 들어감")
        duration = c.seconds

    background = _background(c, fetch, stem.with_name(f"{stem.name}_bg.png"), font, notes)
    overlays = []
    if c.caption:
        overlays.append(Overlay(caption_png(c.caption, stem.with_name(f"{stem.name}_cap.png"), font,
                                             center_y=CAPTION_Y, one_line=True)))
    for i, cue in enumerate(line_cues(lines, speech.words, spoken)):
        png = subtitle_png(cue.text, stem.with_name(f"{stem.name}_sub{i}.png"), font)
        overlays.append(Overlay(png, cue.start, cue.stop))

    return make_segment(stem.with_suffix(".mp4"), background, audio, duration, overlays, zoom=c.kind == "이미지")
