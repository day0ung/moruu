"""장면 목록 + 바이블 + TTS → Timeline. 줄마다 TTS 를 부르고 자막 시각을 정한다."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from channels.tts import narration
from channels.tts.google import Part, Speech
from channels.tts.srt import line_cues
from channels.video.ffmpeg import media_duration
from channels.video.timeline import Clip, Scene, Subtitle, Timeline
from pipelines.ai_drama.bible import Character
from pipelines.ai_drama.script import DramaScene

SIZE = (1920, 1080)
LINE_MAX = 24  # 가로 화면 자막 한 줄 글자 수
GAP = 0.4  # 줄 사이 쉼(초)
SCENE_TAIL = 1.0  # 장면 마지막 줄 뒤 여유(초)


class TTS(Protocol):
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech: ...


def build_timeline(scenes: list[DramaScene], cast: Mapping[str, Character], tts: TTS,
                   lexicon: Mapping[str, str], work: Path, music: Mapping[str, Path]) -> Timeline:
    work.mkdir(parents=True, exist_ok=True)
    out = []
    for s in scenes:
        t, clips, subs = 0.0, [], []
        for i, sp in enumerate(s.lines):
            who = cast[sp.speaker]
            lines = narration.to_lines(sp.raw, lexicon, LINE_MAX)
            speech = tts.synthesize_parts([p for x in lines for p in x.parts], who.voice, who.rate, who.pitch)
            audio = work / f"{s.number:03}_{i:03}.mp3"
            audio.write_bytes(speech.audio)
            spoken = speech.end if speech.end is not None else media_duration(audio)
            clips.append(Clip(audio, t))
            subs += [Subtitle(c.text, who.color, t + c.start, t + c.stop)
                     for c in line_cues(lines, speech.words, spoken)]
            t += spoken + GAP
        duration = max(t - GAP, 0.0) + SCENE_TAIL
        out.append(Scene(s.number, s.title, s.image, music.get(s.music) if s.music else None,
                         duration, tuple(clips), tuple(subs)))
    return Timeline(*SIZE, tuple(out))
