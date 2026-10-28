"""단어 시각 → 쇼츠용 자막(SRT). 몇 단어씩 묶어 크게 띄운다."""
from __future__ import annotations

from channels.tts.google import Word

TAIL = 0.6  # 끝 시각을 모를 때 마지막 자막을 보여 줄 시간(초)


def _ts(sec: float) -> str:
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def to_srt(words: list[Word], end: float | None, per: int = 3) -> str:
    chunks = [words[i:i + per] for i in range(0, len(words), per)]
    out = []
    for n, chunk in enumerate(chunks):
        start = chunk[0].start
        if n + 1 < len(chunks):
            stop = chunks[n + 1][0].start
        else:
            stop = end if end is not None else chunk[-1].start + TAIL
        out.append(f"{n + 1}\n{_ts(start)} --> {_ts(stop)}\n{' '.join(w.text for w in chunk)}\n")
    return "\n".join(out)
