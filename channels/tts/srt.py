"""TTS 시각 → 자막. 단어 몇 개씩(cues) 또는 대본 줄 단위(line_cues)."""
from __future__ import annotations

from dataclasses import dataclass

from channels.tts.google import Word
from channels.tts.narration import Line

TAIL = 0.6  # 끝 시각을 모를 때 마지막 자막을 보여 줄 시간(초)


@dataclass(frozen=True)
class Cue:
    start: float
    stop: float
    text: str


def _ts(sec: float) -> str:
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def cues(words: list[Word], end: float | None, per: int = 3) -> list[Cue]:
    chunks = [words[i:i + per] for i in range(0, len(words), per)]
    out = []
    for n, chunk in enumerate(chunks):
        if n + 1 < len(chunks):
            stop = chunks[n + 1][0].start
        else:
            stop = end if end is not None else chunk[-1].start + TAIL
        out.append(Cue(chunk[0].start, stop, " ".join(w.text for w in chunk)))
    return out


def line_cues(lines: list[Line], words: list[Word], end: float) -> list[Cue]:
    """자막 한 줄 = 그 줄 첫 조각의 시각부터 다음 줄 시작까지.

    words 는 synthesize_parts 결과 (조각마다 하나). 시각이 없으면 글자 수 비율로 end 까지 나눈다.
    """
    firsts, n = [], 0
    for line in lines:
        firsts.append(n)
        n += len(line.parts)
    if len(words) == n:
        starts = [words[i].start for i in firsts]
    else:
        total = sum(len(x.shown) for x in lines) or 1
        starts, acc = [], 0
        for x in lines:
            starts.append(end * acc / total)
            acc += len(x.shown)
    stops = [*starts[1:], end]
    return [Cue(a, b, x.shown) for a, b, x in zip(starts, stops, lines)]


def to_srt(words: list[Word], end: float | None, per: int = 3) -> str:
    return "\n".join(
        f"{n + 1}\n{_ts(c.start)} --> {_ts(c.stop)}\n{c.text}\n" for n, c in enumerate(cues(words, end, per))
    )
