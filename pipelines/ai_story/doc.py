"""기획안·대본 ↔ Notion 블록.

기획 페이지: 토글 `📋 기획안` 하나 (렌더는 맨 위 블록만 읽으므로 토글 안은 무시된다). 사람이 토글 안을 고친다.
대본: `# 챕터 N · 제목`(제목1, 이어 쓰기 기준) → `## 장면 K · 제목 #음악 태그` → 콜아웃 🖼 그림 프롬프트 → 대사 문단.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NARRATOR = "내레이션"  # 드라마 바이블과 같은 이름 (pipelines 끼리 import 금지라 따로 둠)

PLAN_TOGGLE = "📋 기획안"
REVIEW_TOGGLE = "🔍 검수 기록"
_CHUNK = 1800  # Notion rich_text 한 덩어리 2000자 제한보다 작게
_CHAPTER = re.compile(r"^챕터\s*(\d+)\s*[·.:\-]?\s*(.*)$")


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[i:i + _CHUNK]}} for i in range(0, len(text), _CHUNK)] or []


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


def callout(text: str, emoji: str) -> dict:
    return _block("callout", text, icon={"type": "emoji", "emoji": emoji}, color="gray_background")


def toggle(text: str, children: list[dict]) -> dict:
    return _block("toggle", text, children=children)


def plain(block: dict) -> str:
    body = block.get(block.get("type")) or {}
    return "".join(r.get("plain_text") or r.get("text", {}).get("content", "") for r in body.get("rich_text", []))


# ── 기획안 ──────────────────────────────────────────────

def plan_blocks(plan: dict) -> list[dict]:
    """기획안 JSON → [토글]. plan: titles, thumbnail, synopsis, characters[{name, desc}], chapters[{title, beats}], twist."""
    kids = [h3("제목 후보"), *[bullet(t) for t in plan.get("titles", [])],
            h3("썸네일 문구"), para(plan.get("thumbnail", "")),
            h3("시놉시스"), para(plan.get("synopsis", "")),
            h3("이번 회차 인물"), *[bullet(f"{c.get('name', '')} — {c.get('desc', '')}") for c in plan.get("characters", [])]]
    for i, ch in enumerate(plan.get("chapters", []), 1):
        kids += [h3(f"챕터 {i} · {ch.get('title', '')}"), *[bullet(b) for b in ch.get("beats", [])]]
    kids += [h3("반전과 복선 회수"), para(plan.get("twist", ""))]
    return [toggle(PLAN_TOGGLE, kids)]


@dataclass
class PlanText:
    text: str  # 사람이 고친 기획안 전체 (프롬프트용)
    chapters: list[tuple[str, str]] = field(default_factory=list)  # (제목, 그 챕터 글자)
    characters: list[tuple[str, str]] = field(default_factory=list)  # (이름, 설명)


def read_plan(blocks: list[dict]) -> PlanText:
    """토글 안 블록 → 글자. ### 제목으로 구역을 나눈다."""
    lines, sections, current = [], [], None
    for b in blocks:
        text = plain(b).strip()
        if b.get("type") == "heading_3":
            current = [text, []]
            sections.append(current)
            lines.append(f"\n## {text}")
        elif text:
            lines.append(f"- {text}" if b.get("type") == "bulleted_list_item" else text)
            if current:
                current[1].append(text)
    out = PlanText("\n".join(lines).strip())
    for title, body in sections:
        m = _CHAPTER.match(title)
        if m:
            out.chapters.append((m[2].strip(), "\n".join(body)))
        elif title.startswith("이번 회차 인물"):
            for item in body:
                name, _, desc = item.partition("—")
                if name.strip():
                    out.characters.append((name.strip(), desc.strip()))
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


def chapter_blocks(number: int, title: str, scenes: list[dict], first_scene: int) -> list[dict]:
    blocks = [h1(f"챕터 {number} · {title}")]
    for k, s in enumerate(scenes, first_scene):
        music = (s.get("music") or "").strip()
        blocks.append(h2(f"장면 {k} · {s.get('title', '').strip()}" + (f" #음악 {music}" if music else "")))
        if s.get("image_prompt"):
            blocks.append(callout(f"{k:02}.png — {s['image_prompt']}", "🖼"))
        chunk: list[str] = []
        for line in (line_text(x) for x in s.get("lines", [])):
            if chunk and len("\n".join(chunk + [line])) > _CHUNK:
                blocks.append(para("\n".join(chunk)))
                chunk = []
            chunk.append(line)
        if chunk:
            blocks.append(para("\n".join(chunk)))
    return blocks


def written(blocks: list[dict]) -> tuple[int, int]:
    """(이미 쓴 챕터 수, 다음 장면 번호)."""
    chapters = sum(1 for b in blocks if b.get("type") == "heading_1" and _CHAPTER.match(plain(b).strip()))
    scenes = sum(1 for b in blocks if b.get("type") == "heading_2")
    return chapters, scenes + 1


def find_toggle(blocks: list[dict], title: str) -> str | None:
    return next((b["id"] for b in blocks if b.get("type") == "toggle" and plain(b).strip() == title), None)
