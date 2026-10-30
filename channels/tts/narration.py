"""대사 한 줄 → 자막 줄 + 읽을 조각.

  {3M|쓰리엠}  화면엔 "3M", 소리는 "쓰리엠"
  [쉼 0.5]     0.5초 멈춤 (화면엔 안 보임)
  발음 사전    {…} 밖의 글자에 적용. 띄어쓰기로 나뉜 낱말 안에서만 바꾼다.

자막 한 줄이 max_chars 를 넘으면 띄어쓰기 자리 중 가운데에 가까운 곳(쉼표·마침표 뒤 우선)에서 나눈다.
{…} 안이나 "3M을" 처럼 붙은 글자 사이에서는 나누지 않는다.
한 글자 낱말(번·수·것·곳, 이·그 …) 앞뒤는 되도록 피한다 — "여러 / 번" 처럼 갈라지지 않게.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from channels.tts.google import Part

_TOKEN = re.compile(r"\{([^{}|]*)\|([^{}]*)\}|\[쉼\s*(\d+(?:\.\d+)?)\]")
_BAD_READING = re.compile(r"[{}|]")
_BAD_PAUSE = re.compile(r"\[쉼")
_BRACKET = re.compile(r"[\[\]]")  # [쉼] 오타([쉬 0.5] 등)가 그대로 읽히지 않게
_STOP = ",.?!…~"
_STOP_BONUS = 3  # 쉼표·마침표 뒤를 이만큼 가운데에 가깝게 쳐 준다 (글자 수)
_SHORT_PENALTY = 3  # 한 글자 낱말 앞뒤는 이만큼 멀게 친다


@dataclass(frozen=True)
class Line:
    shown: str  # 자막에 보일 글자
    parts: tuple[Part, ...]  # 읽을 조각 (쉼마다 나뉨)


@dataclass
class _Atom:
    shown: str
    spoken: str
    pause: float = 0.0

    @property
    def breakable(self) -> bool:
        """이 뒤에서 줄을 나눌 수 있나 — 띄어쓰기나 쉼 뒤만."""
        return self.shown[-1:].isspace() or self.pause > 0


def problems(raw: str) -> list[str]:
    rest = _TOKEN.sub("", raw)
    out = []
    if _BAD_READING.search(rest):
        out.append("읽는 법 {글자|읽기} 형식 오류")
    if _BAD_PAUSE.search(rest):
        out.append("쉼 [쉼 0.5] 형식 오류")
    elif _BRACKET.search(rest):
        out.append("대괄호 [ ] 는 [쉼 0.5] 만 — 오타 확인")
    return out


def _say(word: str, lexicon: Mapping[str, str]) -> str:
    for key in sorted(lexicon, key=len, reverse=True):
        word = word.replace(key, lexicon[key])
    return word


def _atoms(raw: str, lexicon: Mapping[str, str]) -> list[_Atom]:
    atoms: list[_Atom] = []

    def plain(text: str) -> None:
        for piece in re.findall(r"\s+|\S+\s*", text):
            if piece.isspace():
                if atoms:
                    atoms[-1].shown += piece
                    atoms[-1].spoken += piece
            else:
                atoms.append(_Atom(piece, _say(piece, lexicon)))

    pos = 0
    for m in _TOKEN.finditer(raw):
        plain(raw[pos:m.start()])
        if m[3] is not None:
            if atoms:
                atoms[-1].pause += float(m[3])
            else:
                atoms.append(_Atom("", "", float(m[3])))
        else:
            atoms.append(_Atom(m[1], m[2]))
        pos = m.end()
    plain(raw[pos:])
    return atoms


def _width(atoms: list[_Atom]) -> int:
    return len("".join(a.shown for a in atoms).strip())


def _split(atoms: list[_Atom], max_chars: int) -> list[list[_Atom]]:
    total = _width(atoms)
    cuts = [k for k in range(len(atoms) - 1) if atoms[k].breakable]
    if total <= max_chars or not cuts:
        return [atoms]

    def score(k: int) -> float:
        left = _width(atoms[:k + 1])
        bonus = _STOP_BONUS if atoms[k].shown.rstrip()[-1:] in tuple(_STOP) else 0
        short = any(len(a.shown.strip()) == 1 for a in (atoms[k], atoms[k + 1]))
        return abs(left - total / 2) - bonus + (_SHORT_PENALTY if short else 0)

    k = min(cuts, key=score)
    return _split(atoms[:k + 1], max_chars) + _split(atoms[k + 1:], max_chars)


def _line(atoms: list[_Atom]) -> Line:
    parts: list[Part] = []
    buf = ""
    for a in atoms:
        buf += a.spoken
        if a.pause:
            parts.append(Part(" ".join(buf.split()), a.pause))
            buf = ""
    if buf.strip() or not parts:
        parts.append(Part(" ".join(buf.split())))
    return Line(" ".join("".join(a.shown for a in atoms).split()), tuple(parts))


def to_lines(raw: str, lexicon: Mapping[str, str], max_chars: int) -> list[Line]:
    atoms = _atoms(raw, lexicon)
    return [_line(chunk) for chunk in _split(atoms, max_chars)] if atoms else []
