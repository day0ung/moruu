"""Notion 페이지 본문 블록 → 컷 목록 + 검사.

형식 (docs/notion-schema.md):
  [이미지 블록, 캡션 = 출처]       ← 선택. 없으면 폴더 파일, 그것도 없으면 카드
  > 화면 문구 **강조**              ← 인용 블록, 선택. 굵게 = 노란 강조
  대사 한 줄 = 자막 한 줄 #남 #4초   ← 줄 끝 태그: 목소리 남/여, 길이 고정(초)
  (빈 줄)                           ← 다음 컷
이미지·인용 블록도 새 컷을 연다 (지금 컷에 이미 대사가 있으면). 그 밖의 블록(제목, 코드 블록 프롬프트, 콜아웃)은 무시한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from channels.tts import narration
from channels.video.frames import Span
from core.safety import banned_words

CAPTION_MAX = 30
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXT = (".mp4", ".mov")
SOURCES_FILE = "출처.txt"
_TAG = re.compile(r"\s*#(남|여|\d+(?:\.\d+)?초)(?=\s|$)")
_SOURCE_LINE = re.compile(r"^\s*(\d+)\s*:\s*(.+)$")


@dataclass
class Cut:
    number: int
    caption: list[Span] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)  # 태그를 뺀 대사 줄 ({…}·[쉼] 그대로)
    image_url: str | None = None
    image_path: Path | None = None
    image_source: str = ""
    voice: str = ""  # 남 / 여 / "" = 페이지 기본
    seconds: float | None = None  # #N초

    @property
    def kind(self) -> str:
        return "이미지" if self.image_url or self.image_path else "카드"

    @property
    def caption_text(self) -> str:
        return "".join(s.text for s in self.caption)

    @property
    def narration(self) -> str:
        return " ".join(self.lines)


def _plain(rich: list[dict]) -> str:
    return "".join(r.get("plain_text", "") for r in rich)


def _spans(rich: list[dict]) -> list[Span]:
    spans = []
    for r in rich:
        text = r.get("plain_text", "")
        if not spans:
            text = text.lstrip()
        if text:
            spans.append(Span(text, bool(r.get("annotations", {}).get("bold"))))
    return spans


def _take_tags(cut: Cut, line: str) -> str:
    for tag in _TAG.findall(line):
        if tag in ("남", "여"):
            cut.voice = tag
        else:
            cut.seconds = float(tag[:-1])
    return _TAG.sub("", line).strip()


def parse_cuts(blocks: list[dict]) -> list[Cut]:
    cuts: list[Cut] = []
    closed = True  # 빈 줄 뒤 — 다음 내용이 새 컷을 연다

    def current(new_if: bool) -> Cut:
        nonlocal closed
        if closed or not cuts or new_if:
            cuts.append(Cut(len(cuts) + 1))
            closed = False
        return cuts[-1]

    for b in blocks:
        kind = b.get("type")
        body = b.get(kind) or {}
        last = cuts[-1] if cuts else None
        if kind == "image":
            cut = current(bool(last and (last.lines or last.image_url)))
            cut.image_url = body.get(body.get("type", ""), {}).get("url")
            cut.image_source = _plain(body.get("caption", [])).strip()
        elif kind == "quote":
            cut = current(bool(last and (last.lines or last.caption)))
            cut.caption = _spans(body.get("rich_text", []))
        elif kind == "paragraph":
            text = _plain(body.get("rich_text", []))
            if not text.strip():
                closed = True
                continue
            cut = current(False)
            cut.lines += [x for x in (_take_tags(cut, line) for line in text.split("\n")) if x]
    return cuts


def _sources(folder: Path) -> tuple[dict[int, str], str]:
    path = folder / SOURCES_FILE
    by_number, default = {}, ""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _SOURCE_LINE.match(line)
            if m:
                by_number[int(m[1])] = m[2].strip()
            elif line.strip():
                default = line.strip()
    return by_number, default


def attach_folder(cuts: list[Cut], folder: Path) -> list[str]:
    """folder 의 01.png, 2.jpg … 를 같은 번호 컷의 화면으로. Notion 이미지가 있는 컷은 그대로 둔다."""
    if not folder.is_dir():
        return []
    by_number, default = _sources(folder)
    out = []
    for f in sorted(folder.iterdir()):
        ext = f.suffix.lower()
        if not f.stem.isdigit() or ext not in IMAGE_EXT + VIDEO_EXT:
            continue
        n = int(f.stem)
        if ext in VIDEO_EXT:
            out.append(f"{f.name}: 영상 컷은 아직 지원 안 함")
        elif n > len(cuts):
            out.append(f"{f.name}: {n}번 컷 없음")
        elif not cuts[n - 1].image_url:
            cuts[n - 1].image_path = f
            cuts[n - 1].image_source = by_number.get(n, default)
    return out


def script_problems(cuts: list[Cut], disclosure: str) -> list[str]:
    if not cuts:
        return ["컷 없음 — 본문에 대사를 쓰고, 컷 사이는 빈 줄"]
    out = []
    for c in cuts:
        tag = f"컷 {c.number}"
        if not c.lines:
            out.append(f"{tag}: 대사 없음")
        if c.image_url and not c.image_source:
            out.append(f"{tag}: 이미지 캡션에 출처 없음")
        if c.image_path and not c.image_source:
            out.append(f"{tag}: {c.image_path.name} 출처 없음 — {SOURCES_FILE} 에 적기")
        if len(c.caption_text) > CAPTION_MAX:
            out.append(f"{tag}: 화면 문구 {CAPTION_MAX}자 초과 ({len(c.caption_text)}자)")
        out += [f"{tag}: {p}" for line in c.lines for p in narration.problems(line)]
        for w in banned_words(c.caption_text + " " + c.narration):
            out.append(f"{tag}: 금지어 {w}")
    if not disclosure.strip():
        out.append("대가성문구 비어 있음")
    return out
