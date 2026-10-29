"""Notion 페이지 본문 블록 → 장면 목록 + 검사.

형식 (docs/superpowers/specs/2026-10-29-shopping-shorts-render-design.md):
  ## 장면 N · 카드|이미지|AI영상
  [이미지 블록, 캡션 = 출처]
  화면: 굵게 = 노란 강조
  내레이션: 읽을 문장
그 밖의 블록(코드 블록 프롬프트, 안내 문단, 콜아웃)은 무시한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from channels.video.frames import Span
from core.safety import banned_words

KINDS = ("카드", "이미지", "AI영상")
CAPTION_MAX = 30
_SCENE = re.compile(r"^\s*장면\s*(\d+)\s*[·・:\-]\s*(\S+)")
_CAPTION = "화면:"
_NARRATION = "내레이션:"


@dataclass
class Scene:
    number: int
    kind: str
    caption: list[Span] = field(default_factory=list)
    narration: str = ""
    image_url: str | None = None
    image_source: str = ""

    @property
    def caption_text(self) -> str:
        return "".join(s.text for s in self.caption)


def _plain(rich: list[dict]) -> str:
    return "".join(r.get("plain_text", "") for r in rich)


def _spans(rich: list[dict], skip: int) -> list[Span]:
    """rich_text → Span. 앞 skip 글자(접두어 "화면:")와 그 뒤 공백은 뺀다."""
    spans = []
    for r in rich:
        text = r.get("plain_text", "")
        if skip:
            cut = min(skip, len(text))
            text, skip = text[cut:], skip - cut
        if not spans:
            text = text.lstrip()
        if text:
            spans.append(Span(text, bool(r.get("annotations", {}).get("bold"))))
    return spans


def parse_scenes(blocks: list[dict]) -> list[Scene]:
    scenes: list[Scene] = []
    cur: Scene | None = None
    for b in blocks:
        kind = b.get("type")
        body = b.get(kind) or {}
        if kind in ("heading_1", "heading_2", "heading_3"):
            m = _SCENE.match(_plain(body.get("rich_text", [])))
            cur = Scene(int(m[1]), m[2]) if m else None
            if cur:
                scenes.append(cur)
        elif cur is None:
            continue
        elif kind == "image":
            src = body.get(body.get("type", ""), {})
            cur.image_url = src.get("url")
            cur.image_source = _plain(body.get("caption", [])).strip()
        elif kind == "paragraph":
            rich = body.get("rich_text", [])
            text = _plain(rich).strip()
            if text.startswith(_CAPTION):
                cur.caption = _spans(rich, _plain(rich).index(_CAPTION) + len(_CAPTION))
            elif text.startswith(_NARRATION):
                cur.narration = text[len(_NARRATION):].strip()
    return scenes


def script_problems(scenes: list[Scene], disclosure: str) -> list[str]:
    if not scenes:
        return ["장면 없음 — '## 장면 N · 카드|이미지' 제목 확인"]
    out = []
    for s in scenes:
        tag = f"장면 {s.number}"
        if s.kind not in KINDS:
            out.append(f"{tag}: 장면 종류 '{s.kind}' — {'/'.join(KINDS)} 중 하나")
        elif s.kind == "AI영상":
            out.append(f"{tag}: AI영상 은 아직 지원 안 함")
        if not s.narration:
            out.append(f"{tag}: 내레이션 없음")
        if s.kind == "이미지":
            if not s.image_url:
                out.append(f"{tag}: 이미지 없음")
            elif not s.image_source:
                out.append(f"{tag}: 이미지 캡션에 출처 없음")
        if len(s.caption_text) > CAPTION_MAX:
            out.append(f"{tag}: 화면 문구 {CAPTION_MAX}자 초과 ({len(s.caption_text)}자)")
        for w in banned_words(s.caption_text + " " + s.narration):
            out.append(f"{tag}: 금지어 {w}")
    if not disclosure.strip():
        out.append("대가성문구 비어 있음")
    return out
