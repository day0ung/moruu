"""시리즈 바이블 표 → 인물별 목소리·높낮이·빠르기·자막색.

머리글로 칸을 찾는다 (순서 무관): 인물 | 목소리 | 높낮이 | 빠르기 | 자막색. 다른 칸(나이·성격, 그림 설명)은 무시.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NARRATOR = "내레이션"
COLORS = {"흰색": "#FFFFFF", "노랑": "#FFD400", "하늘": "#7FD3FF", "연두": "#A8E063",
          "분홍": "#FF9EC4", "주황": "#FFB347", "보라": "#C3A6FF"}
AUTO = ["노랑", "하늘", "연두", "분홍", "주황", "보라"]
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


@dataclass(frozen=True)
class Character:
    name: str
    voice: str
    pitch: float  # 반음
    rate: float
    color: str  # #RRGGBB


def _number(text: str, low: float, high: float) -> float | None:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if low <= value <= high else None


def _color(name: str, raw: str) -> tuple[str, str | None]:
    """(색, 문제). 비어 있으면 색 "" — 나중에 자동 배정 (내레이션은 흰색)."""
    if raw in COLORS:
        return COLORS[raw], None
    if _HEX.fullmatch(raw):
        return raw.upper(), None
    if not raw:
        return (COLORS["흰색"] if name == NARRATOR else ""), None
    return COLORS["흰색"], f"바이블: {name} 자막색 모름 ({raw}) — {'·'.join(COLORS)} 또는 #RRGGBB"


def parse_bible(tables: list[list[list[str]]], default_rate: float) -> tuple[dict[str, Character], list[str]]:
    table = next((t for t in tables if t and "인물" in t[0] and "목소리" in t[0]), None)
    if table is None:
        return {}, ["바이블 표 없음 — 머리글에 인물·목소리 칸"]
    head = table[0]

    def col(row: list[str], name: str) -> str:
        i = head.index(name) if name in head else len(row)
        return row[i].strip() if i < len(row) else ""

    problems: list[str] = []
    rows: list[list] = []
    for row in table[1:]:
        name = col(row, "인물")
        if not name:
            continue
        voice = col(row, "목소리")
        if not voice:
            problems.append(f"바이블: {name} 목소리 없음")
        pitch_raw, rate_raw = col(row, "높낮이"), col(row, "빠르기")
        pitch = _number(pitch_raw, -20, 20) if pitch_raw else 0.0
        if pitch is None:
            problems.append(f"바이블: {name} 높낮이 -20~20 아님 ({pitch_raw})")
        rate = _number(rate_raw, 0.25, 4.0) if rate_raw else default_rate
        if rate is None:
            problems.append(f"바이블: {name} 빠르기 0.25~4.0 아님 ({rate_raw})")
        color, problem = _color(name, col(row, "자막색"))
        if problem:
            problems.append(problem)
        rows.append([name, voice, pitch or 0.0, rate or default_rate, color])

    used = {r[4] for r in rows}
    free = [COLORS[c] for c in AUTO if COLORS[c] not in used] or [COLORS[c] for c in AUTO]
    auto = [r for r in rows if not r[4]]
    for i, r in enumerate(auto):
        r[4] = free[i % len(free)]
    if not any(r[0] == NARRATOR for r in rows):
        problems.append(f"바이블: {NARRATOR} 줄 없음")
    return {r[0]: Character(*r) for r in rows}, problems
