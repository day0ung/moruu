"""기획안·대본 ↔ Notion 블록. 페이지 하나를 위에서 아래로 읽는 '대본집' 배치.

  [기획 구역]  로그라인·시청 포인트·첫 30초 오프닝·제목 후보·썸네일·시놉시스·인물·구성표(표)·장면 구성(챕터별 토글)·반전
               — 문단(paragraph)·제목2 를 쓰지 않는다 (렌더가 대사·장면으로 읽으므로). 구분선(divider)으로 끝.
  [대본 정보]  대본을 다 쓰면 구분선 바로 뒤에 넣는다: 예상 길이·글자 수·검수 결과·목차(챕터별 시작 시각)
  [대본]       # 챕터 N · 제목 → ▸ 🔍 검수·그림 (접힘) → ## 장면 K · 제목 #음악 태그 → 대사 문단
  [끝]         ▸ 🖼 그림 목록 (접힘, 그림 만들 때 한곳에서)
사람은 기획 구역을 고친다. 대본 AI 는 고친 그대로 따른다.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

NARRATOR = "내레이션"  # 드라마 바이블과 같은 이름 (pipelines 끼리 import 금지라 따로 둠)

CHAPTER_TOGGLE = "🔍 검수·그림"
IMAGE_TOGGLE = "🖼 그림 목록"
_CHUNK = 1800  # Notion rich_text 한 덩어리 2000자 제한보다 작게
_CHAPTER = re.compile(r"^챕터\s*(\d+)\s*[·.:\-]?\s*(.*?)\s*(?:\(약\s*[\d.]+\s*분\))?$")
_IMAGE_LINE = re.compile(r"^\d{2,}\.png — ")
TABLE_HEAD = ["챕터", "분", "핵심 사건", "감정", "복선·회수"]


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[i:i + _CHUNK]}} for i in range(0, len(text), _CHUNK)]


def _block(kind: str, text: str, **extra) -> dict:
    return {"type": kind, kind: {"rich_text": rt(text), **extra}}


def h1(text: str) -> dict:
    return _block("heading_1", text)


def h2(text: str) -> dict:
    return _block("heading_2", text)


def h3(text: str) -> dict:
    return _block("heading_3", text)


def para(text: str) -> dict:
    return _block("paragraph", text)


def bullet(text: str) -> dict:
    return _block("bulleted_list_item", text)


def quote(text: str) -> dict:
    return _block("quote", text)


def callout(text: str, emoji: str, children: list[dict] | None = None) -> dict:
    extra = {"icon": {"type": "emoji", "emoji": emoji}, "color": "gray_background"}
    if children:
        extra["children"] = children
    return _block("callout", text, **extra)


def toggle(text: str, children: list[dict]) -> dict:
    return _block("toggle", text, children=children)


def divider() -> dict:
    return {"type": "divider", "divider": {}}


def table(rows: list[list[str]]) -> dict:
    return {"type": "table", "table": {"table_width": len(rows[0]), "has_column_header": True, "has_row_header": False,
                                       "children": [{"type": "table_row", "table_row": {"cells": [rt(c) for c in row]}}
                                                    for row in rows]}}


def plain(block: dict) -> str:
    body = block.get(block.get("type")) or {}
    if block.get("type") == "table_row":
        return " | ".join("".join(r.get("plain_text") or r.get("text", {}).get("content", "") for r in cell)
                          for cell in body.get("cells", []))
    return "".join(r.get("plain_text") or r.get("text", {}).get("content", "") for r in body.get("rich_text", []))


# ── 기획 ────────────────────────────────────────────────

def chapter_label(number: int, title: str, minutes: float | None = None) -> str:
    return f"챕터 {number} · {title}" + (f" (약 {minutes:g}분)" if minutes else "")


def plan_blocks(plan: dict) -> list[dict]:
    """기획안 JSON → 기획 구역 블록 (구분선으로 끝).

    plan: titles, thumbnail, logline, hook, opening, synopsis, characters[{name, desc, arc}],
          chapters[{title, minutes, event, emotion, foreshadow, scenes[]}], twist
    """
    chapters = plan.get("chapters", [])
    out = [callout(plan.get("logline", ""), "💡"),
           h3("시청 포인트"), bullet(plan.get("hook", "")),
           h3("첫 30초 오프닝"), quote(plan.get("opening", "")),
           h3("제목 후보"), *[bullet(t) for t in plan.get("titles", [])],
           h3("썸네일 문구"), bullet(plan.get("thumbnail", "")),
           h3("시놉시스"), quote(plan.get("synopsis", "")),
           h3("이번 회차 인물"),
           *[bullet(f"{c.get('name', '')} — {c.get('desc', '')}" + (f" (변화: {c['arc']})" if c.get("arc") else ""))
             for c in plan.get("characters", [])]]
    if chapters:
        out += [h3("구성표"), table([TABLE_HEAD] + [
            [str(i), f"{c.get('minutes', '')}", c.get("event", ""), c.get("emotion", ""), c.get("foreshadow", "")]
            for i, c in enumerate(chapters, 1)])]
    out.append(h3("장면 구성"))
    out += [toggle(chapter_label(i, c.get("title", ""), c.get("minutes")), [bullet(s) for s in c.get("scenes", [])])
            for i, c in enumerate(chapters, 1)]
    out += [h3("반전과 복선 회수"), bullet(plan.get("twist", "")), divider()]
    return out


@dataclass
class PlanText:
    text: str  # 사람이 고친 기획 구역 전체 (프롬프트용)
    chapters: list[tuple[str, str]] = field(default_factory=list)  # (제목, 장면 구성)
    characters: list[tuple[str, str]] = field(default_factory=list)  # (이름, 설명)
    minutes: list[float] = field(default_factory=list)  # 챕터별 예상 분 (모르면 0)
    end_id: str = ""  # 기획 구역 끝 구분선 블록 ID


def read_plan(blocks: list[dict], children: Callable[[str], list[dict]]) -> PlanText:
    """페이지 맨 위 블록들 → 기획. 구분선(또는 첫 챕터 제목1)에서 멈춘다. 토글·표 안은 children(id) 로 읽는다."""
    out = PlanText("")
    lines: list[str] = []
    section = ""
    for b in blocks:
        kind = b.get("type")
        if kind == "divider":
            out.end_id = b.get("id", "")
            break
        if kind == "heading_1":
            break
        text = plain(b).strip()
        if kind == "heading_3":
            section = text
            lines.append(f"\n## {text}")
        elif kind == "toggle":
            m = _CHAPTER.match(text)
            body = [plain(k).strip() for k in children(b["id"]) if plain(k).strip()]
            lines.append(f"### {text}\n" + "\n".join(f"- {x}" for x in body))
            if m:
                minutes = re.search(r"약\s*([\d.]+)\s*분", text)
                out.chapters.append((m[2].strip(), "\n".join(body)))
                out.minutes.append(float(minutes[1]) if minutes else 0.0)
        elif kind == "table":
            lines += [plain(r) for r in children(b["id"])]
        elif text:
            lines.append(f"- {text}" if kind == "bulleted_list_item" else text)
            if section.startswith("이번 회차 인물") and kind == "bulleted_list_item":
                name, _, desc = text.partition("—")
                if name.strip():
                    out.characters.append((name.strip(), desc.strip()))
    out.text = "\n".join(lines).strip()
    return out


# ── 대본 ────────────────────────────────────────────────

def line_text(line: dict) -> str:
    speaker, text = line.get("speaker", NARRATOR).strip(), line.get("text", "").strip()
    if speaker == NARRATOR:
        return text
    emotion = line.get("emotion", "").strip()
    return f"{speaker}({emotion}): {text}" if emotion else f"{speaker}: {text}"


def scenes_text(scenes: list[dict]) -> str:
    out = []
    for s in scenes:
        out.append(f"[장면] {s.get('title', '')}")
        out += [line_text(x) for x in s.get("lines", [])]
    return "\n".join(out)


def image_line(number: int, prompt: str) -> str:
    return f"{number:02}.png — {prompt}"


def chapter_blocks(number: int, title: str, scenes: list[dict], first_scene: int, note: str = "") -> list[dict]:
    """# 챕터 → ▸ 검수·그림(접힘) → 장면들. 그림 프롬프트는 본문이 아니라 접힌 토글에."""
    images = [bullet(image_line(k, s["image_prompt"])) for k, s in enumerate(scenes, first_scene) if s.get("image_prompt")]
    blocks = [h1(f"챕터 {number} · {title}"), toggle(CHAPTER_TOGGLE, ([bullet(note)] if note else []) + images)]
    for k, s in enumerate(scenes, first_scene):
        music = (s.get("music") or "").strip()
        blocks.append(h2(f"장면 {k} · {s.get('title', '').strip()}" + (f" #음악 {music}" if music else "")))
        chunk: list[str] = []
        for line in (line_text(x) for x in s.get("lines", [])):
            if chunk and len("\n".join(chunk + [line])) > _CHUNK:
                blocks.append(para("\n".join(chunk)))
                chunk = []
            chunk.append(line)
        if chunk:
            blocks.append(para("\n".join(chunk)))
    return blocks


def _clock(sec: float) -> str:
    m, s = divmod(round(sec), 60)
    return f"{m:02}:{s:02}"


def info_blocks(chapters: list[tuple[int, str, float]], chars: int, chars_per_min: float, notes: list[str]) -> list[dict]:
    """대본 정보 + 목차. chapters: (번호, 제목, 그 챕터 글자 수). 시작 시각은 글자 수로 어림."""
    total_min = chars / chars_per_min
    warn = [n for n in notes if n.startswith("⚠")]
    head = f"대본 정보 · 약 {total_min:.0f}분 · {chars:,}자 · 챕터 {len(chapters)}개 · 검수 " + \
           (f"미통과 {len(warn)}개" if warn else "모두 통과")
    toc, t = [], 0.0
    for number, title, n in chapters:
        toc.append(bullet(f"{_clock(t * 60)}  챕터 {number} · {title}"))
        t += n / chars_per_min
    return [callout(head, "📌", toc + [bullet(w) for w in warn])]


def image_list_block(lines: list[str]) -> dict:
    return toggle(IMAGE_TOGGLE, [bullet(x) for x in lines])


def written(blocks: list[dict]) -> tuple[int, int]:
    """(이미 쓴 챕터 수, 다음 장면 번호)."""
    chapters = sum(1 for b in blocks if b.get("type") == "heading_1" and _CHAPTER.match(plain(b).strip()))
    scenes = sum(1 for b in blocks if b.get("type") == "heading_2")
    return chapters, scenes + 1


def chapter_toggles(blocks: list[dict]) -> list[tuple[int, str, str]]:
    """대본 구역의 (챕터 번호, 제목, 검수·그림 토글 ID)."""
    out, current = [], None
    for b in blocks:
        if b.get("type") == "heading_1":
            m = _CHAPTER.match(plain(b).strip())
            current = (int(m[1]), m[2].strip()) if m else None
        elif current and b.get("type") == "toggle" and plain(b).strip() == CHAPTER_TOGGLE:
            out.append((*current, b["id"]))
            current = None
    return out


def is_image_line(text: str) -> bool:
    return bool(_IMAGE_LINE.match(text))
