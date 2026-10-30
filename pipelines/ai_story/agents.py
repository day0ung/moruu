"""에이전트 — 기획·작성·검수·그림 프롬프트·요약. 프롬프트는 prompts/*.md ($변수), AI 는 channels.llm 의 LLM."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from string import Template

from pipelines.ai_story.checks import chapter_problems
from pipelines.ai_story.context import Series
from pipelines.ai_story.doc import NARRATOR, PlanText, scenes_text

PROMPTS = Path(__file__).parent / "prompts"
MAX_REVISIONS = 3
log = logging.getLogger("moruu")


def prompt(name: str, **values) -> list[dict]:
    system = (PROMPTS / "system.md").read_text(encoding="utf-8")
    user = Template((PROMPTS / f"{name}.md").read_text(encoding="utf-8")).safe_substitute(
        {k: (v if str(v).strip() else "(없음)") for k, v in values.items()})
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _list(value) -> list:
    return value if isinstance(value, list) else []


def plan(llm, series: Series, topic: str, count: int = 3, minutes: int = 30, chapters: int = 8) -> list[dict]:
    data = llm.chat_json(prompt("plan", count=count, world=series.world, rules=series.rules, cast=series.cast_text(),
                                episodes=series.episodes_text(), topic=topic, minutes=minutes, chapters=chapters), "plan")
    plans = [p for p in _list(data.get("plans") if isinstance(data, dict) else data) if isinstance(p, dict)]
    return [p for p in plans if _list(p.get("chapters"))][:count]


@dataclass
class Chapter:
    number: int
    total: int
    title: str
    beats: str


def write_chapter(llm, series: Series, plan_text: PlanText, ch: Chapter, previous: str, feedback: str,
                  target: int, music: list[str]) -> list[dict]:
    data = llm.chat_json(prompt("write", number=ch.number, total=ch.total, title=ch.title, beats=ch.beats,
                                world=series.world, rules=series.rules, cast=series.cast_text(), plan=plan_text.text,
                                previous=previous, feedback=feedback, target=target,
                                speakers=", ".join(sorted(series.names - {NARRATOR})), music=", ".join(music)), "write")
    scenes = _list(data.get("scenes") if isinstance(data, dict) else data)
    return [s for s in scenes if isinstance(s, dict)]


def review_chapter(llm, series: Series, plan_text: PlanText, ch: Chapter, previous: str,
                   scenes: list[dict]) -> tuple[bool, list[str]]:
    data = llm.chat_json(prompt("review", number=ch.number, total=ch.total, plan=plan_text.text, cast=series.cast_text(),
                                previous=previous, script=scenes_text(scenes)), "review")
    data = data if isinstance(data, dict) else {}
    notes = [str(n) for n in _list(data.get("notes")) if str(n).strip()]
    return str(data.get("verdict", "")).upper().startswith("PASS"), notes


def image_prompts(llm, series: Series, scenes: list[dict]) -> list[str]:
    listing = "\n\n".join(f"{i}. {s.get('title', '')}\n" + scenes_text([s]) for i, s in enumerate(scenes, 1))
    data = llm.chat_json(prompt("image", cast=series.cast_text(), scenes=listing, count=len(scenes)), "light")
    prompts = [str(p) for p in _list(data.get("prompts") if isinstance(data, dict) else data)]
    return (prompts + [""] * len(scenes))[:len(scenes)]


def summarize(llm, plan_text: PlanText, script: str) -> str:
    data = llm.chat_json(prompt("summary", plan=plan_text.text, script=script[:6000]), "light")
    return str(data.get("summary", "")).strip() if isinstance(data, dict) else ""


def write_reviewed(llm, series: Series, plan_text: PlanText, ch: Chapter, previous: str, target: int,
                   music: list[str]) -> tuple[list[dict], str]:
    """작성 → 기계 검사 + AI 검수 → 지적을 붙여 다시 (최대 MAX_REVISIONS 번). (장면들, 검수 기록 한 줄)."""
    feedback = ""
    for attempt in range(MAX_REVISIONS + 1):
        scenes = write_chapter(llm, series, plan_text, ch, previous, feedback, target, music)
        problems = chapter_problems(scenes, series.names, target)
        passed, notes = (False, []) if problems else review_chapter(llm, series, plan_text, ch, previous, scenes)
        if not problems and passed:
            return scenes, f"챕터 {ch.number}: PASS (수정 {attempt}회)"
        issues = problems + notes
        log.info("챕터 %d 수정 %d: %s", ch.number, attempt + 1, "; ".join(issues)[:300])
        feedback = "\n".join(f"- {x}" for x in issues)
    return scenes, f"⚠ 챕터 {ch.number}: 검수 미통과 (수정 {MAX_REVISIONS}회) — " + "; ".join(issues)[:500]
