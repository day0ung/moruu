"""챕터 기계 검사 — AI 검수 전에. 하나라도 있으면 AI 판정과 상관없이 다시 쓰게 한다."""
from __future__ import annotations

import re

from channels.tts import narration
from core.safety import banned_words
from pipelines.ai_story.doc import NARRATOR

CHARS_PER_MIN = 258  # 렌더 엔진 실측 (공백 제외, 줄 사이 쉼 포함)
_LOOKS_LIKE_SPEAKER = re.compile(r"^[^\s:()]{1,8}(\([^)]*\))?:")


def chapter_target(minutes: float, chapters: int) -> int:
    return round(minutes * CHARS_PER_MIN / chapters)


def spoken_chars(scenes: list[dict]) -> int:
    return sum(len(x.get("text", "").replace(" ", "")) for s in scenes for x in s.get("lines", []))


def chapter_problems(scenes: list[dict], speakers: set[str], target: int) -> list[str]:
    out = []
    if not 2 <= len(scenes) <= 12:
        out.append(f"장면 수 {len(scenes)}개 — 3~8개로")
    for i, s in enumerate(scenes, 1):
        if not s.get("lines"):
            out.append(f"장면 {i}: 대사 없음")
        for x in s.get("lines", []):
            who, text = x.get("speaker", ""), x.get("text", "")
            if who not in speakers:
                out.append(f"장면 {i}: '{who}' 는 인물 목록에 없음 — {', '.join(sorted(speakers))} 중에서")
            if who == NARRATOR and _LOOKS_LIKE_SPEAKER.match(text):
                out.append(f"장면 {i}: 내레이션이 '이름:' 으로 시작함 — 문장을 바꿀 것: {text[:20]}")
            out += [f"장면 {i}: {p}" for p in narration.problems(text)]
        for w in banned_words(" ".join(x.get("text", "") for x in s.get("lines", []))):
            out.append(f"장면 {i}: 금지어 '{w}'")
    chars = spoken_chars(scenes)
    if not 0.6 * target <= chars <= 1.4 * target:
        out.append(f"분량 {chars}자 — 목표 {target}자 (±40%)")
    return list(dict.fromkeys(out))
