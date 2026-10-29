"""단어 시각 → 쇼츠용 자막(SRT). 몇 단어씩 묶어 크게 띄운다."""
from __future__ import annotations

from dataclasses import dataclass

from channels.tts.google import Word

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


def to_srt(words: list[Word], end: float | None, per: int = 3) -> str:
    return "\n".join(
        f"{n + 1}\n{_ts(c.start)} --> {_ts(c.stop)}\n{c.text}\n" for n, c in enumerate(cues(words, end, per))
    )
