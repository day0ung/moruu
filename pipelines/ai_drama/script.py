"""Notion 에피소드 본문 블록 → 장면 목록 + 검사.

형식 (docs/notion-schema.md):
  ## 장면 제목 #음악 잔잔         ← 제목2 = 새 장면. 음악 태그 없으면 앞 장면 곡을 이어 감
  그날 저녁, …                    ← 문단 한 줄 = 대사 한 줄. 이름이 없으면 내레이션
  시어머니(서운하게): 너희 …       ← 바이블 인물 이름: 대사 (괄호 = 감정, 지금은 기록만)
그 밖의 블록(콜아웃·인용·코드·제목1·3)은 메모로 무시한다.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from channels.tts import narration
from core.safety import banned_words
from pipelines.ai_drama.bible import NARRATOR

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MUSIC_EXT = (".mp3", ".m4a", ".wav")
SOURCES_FILE = "출처.txt"
_MUSIC_TAG = re.compile(r"\s*#음악\s+(\S+)")
_SPEAKER = re.compile(r"^([^\s:()]{1,8})(?:\(([^)]*)\))?:\s*(.+)$")
_SOURCE_LINE = re.compile(r"^\s*([^:\s]+)\s*:\s*(.+)$")


@dataclass(frozen=True)
class Spoken:
    speaker: str  # 바이블 인물 이름 또는 내레이션
    emotion: str
    raw: str  # {…}·[쉼] 그대로


@dataclass
class DramaScene:
    number: int
    title: str
    music: str | None  # 이어 가기 적용된 음악 태그
    lines: list[Spoken] = field(default_factory=list)
    image: Path | None = None
    image_source: str = ""


def _plain(block: dict) -> str:
    body = block.get(block.get("type")) or {}
    return "".join(r.get("plain_text", "") for r in body.get("rich_text", []))


def parse_episode(blocks: list[dict], names: set[str]) -> tuple[list[DramaScene], list[str]]:
    scenes: list[DramaScene] = []
    problems: list[str] = []
    early = False
    for b in blocks:
        kind = b.get("type")
        if kind == "heading_2":
            text = _plain(b)
            m = _MUSIC_TAG.search(text)
            music = m[1] if m else (scenes[-1].music if scenes else None)
            scenes.append(DramaScene(len(scenes) + 1, _MUSIC_TAG.sub("", text).strip(), music))
        elif kind == "paragraph":
            for line in (x.strip() for x in _plain(b).split("\n")):
                if not line:
                    continue
                if not scenes:
                    early = True
                    continue
                m = _SPEAKER.match(line)
                if m and m[1] in names and m[1] != NARRATOR:
                    scenes[-1].lines.append(Spoken(m[1], m[2] or "", m[3].strip()))
                elif m and m[1] not in names:
                    problems.append(f"장면 {scenes[-1].number}: 인물 '{m[1]}' 바이블에 없음")
                else:
                    scenes[-1].lines.append(Spoken(NARRATOR, "", line))
    if early:
        problems.insert(0, "장면 제목 전에 대사 — 첫 줄은 ## 장면 제목")
    return scenes, problems


def _sources(folder: Path, is_key: Callable[[str], bool]) -> tuple[dict[str, str], str]:
    """출처.txt → ({키: 출처}, 기본 출처). '키: 출처' 줄은 is_key(키) 일 때만 — "AI:Gemini" 같은 줄은 기본 출처."""
    path = folder / SOURCES_FILE
    by_key, default = {}, ""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _SOURCE_LINE.match(line)
            if m and is_key(m[1]):
                by_key[str(int(m[1])) if m[1].isdigit() else m[1]] = m[2].strip()
            elif line.strip():
                default = line.strip()
    return by_key, default


def attach_images(scenes: list[DramaScene], folder: Path) -> list[str]:
    """folder 의 01.png, 2.jpg … 를 같은 번호 장면 그림으로."""
    if not folder.is_dir():
        return []
    by_key, default = _sources(folder, str.isdigit)
    out = []
    for f in sorted(folder.iterdir()):
        if not f.stem.isdigit() or f.suffix.lower() not in IMAGE_EXT:
            continue
        n = int(f.stem)
        if not 1 <= n <= len(scenes):
            out.append(f"{f.name}: {n}번 장면 없음")
            continue
        scenes[n - 1].image = f
        scenes[n - 1].image_source = by_key.get(str(n), default)
    return out


def find_music(tags: set[str], folder: Path) -> tuple[dict[str, Path], list[str]]:
    """음악 태그 → folder/{태그}.mp3 (.m4a/.wav). 출처는 folder/출처.txt 의 '태그: 출처' 또는 기본 줄."""
    by_key, default = _sources(folder, tags.__contains__)
    found, problems = {}, []
    for tag in sorted(tags):
        path = next((folder / f"{tag}{ext}" for ext in MUSIC_EXT if (folder / f"{tag}{ext}").is_file()), None)
        if path is None:
            problems.append(f"음악 '{tag}' 파일 없음 — {tag}.mp3")
            continue
        found[tag] = path
        if not (by_key.get(tag) or default):
            problems.append(f"음악 '{tag}' 출처 없음 — {SOURCES_FILE} 에 적기")
    return found, problems


def script_problems(scenes: list[DramaScene]) -> list[str]:
    if not scenes:
        return ["장면 없음 — 본문에 ## 장면 제목과 대사"]
    out = []
    for s in scenes:
        tag = f"장면 {s.number}"
        if not s.lines:
            out.append(f"{tag}: 대사 없음")
        if s.image is None:
            out.append(f"{tag}: 그림 없음 — {s.number:02}.png")
        elif not s.image_source:
            out.append(f"{tag}: {s.image.name} 출처 없음 — {SOURCES_FILE} 에 적기")
        out += [f"{tag}: {p}" for x in s.lines for p in narration.problems(x.raw)]
        for w in banned_words(" ".join(x.raw for x in s.lines) + " " + s.title):
            out.append(f"{tag}: 금지어 {w}")
    return out
