"""대본 페이지 → Kling 작업 파일 (작업지.md · prompts.csv · 출처.txt).

사람이 Kling 웹에서 인물 기준 이미지 → 장면 그림 순서로 프롬프트를 붙여 넣고, 받은 그림을 `07.png` 이름 그대로
Drive 자료 폴더에 올리면 렌더가 가져간다. 영어 프롬프트가 없는 옛 대본은 AI 로 옮기고, 인물 기준 프롬프트도 AI 로 만든다.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipelines.ai_story import agents
from pipelines.ai_story.checks import CHARS_PER_MIN
from pipelines.ai_story.doc import chapter_toggles, parse_image_line, plain, read_plan, split_speaker

SOURCE_LINE = "AI 생성 이미지: Kling"
_SCENE = re.compile(r"^장면\s*(\d+)\s*·\s*(.*?)(?:\s*#음악\s+\S+)?$")


@dataclass
class SceneImage:
    number: int
    title: str
    seconds: float = 0.0
    people: list[str] = field(default_factory=list)
    ko: str = ""
    en: str = ""


@dataclass
class KlingSheet:
    content_id: str
    title: str
    characters: list[tuple[str, str, str]]  # (이름, 한국어 설명, 영어 기준 프롬프트)
    scenes: list[SceneImage]


def read_scenes(store, blocks: list[dict]) -> list[SceneImage]:
    """대본 구역의 장면들 — 제목·예상 길이·말하는 인물, 그리고 챕터 토글 속 그림 줄."""
    scenes: dict[int, SceneImage] = {}
    current = None
    for b in blocks:
        kind = b.get("type")
        if kind == "heading_2":
            m = _SCENE.match(plain(b).strip())
            current = scenes.setdefault(int(m[1]), SceneImage(int(m[1]), m[2].strip())) if m else None
        elif kind == "paragraph" and current:
            for line in plain(b).split("\n"):
                who, text = split_speaker(line)
                if who and who not in current.people:
                    current.people.append(who)
                current.seconds += len(re.sub(r"\s", "", text)) / CHARS_PER_MIN * 60
    for _, _, toggle_id in chapter_toggles(blocks):
        for k in store.page_blocks(toggle_id):
            parsed = parse_image_line(plain(k))
            if parsed and parsed[0] in scenes:
                scenes[parsed[0]].ko, scenes[parsed[0]].en = parsed[1], parsed[2]
    return [scenes[n] for n in sorted(scenes)]


def build_sheet(store, llm, content_id: str, page_id: str) -> KlingSheet:
    blocks = store.page_blocks(page_id)
    plan = read_plan(blocks, store.page_blocks)
    scenes = read_scenes(store, blocks)
    missing = [s for s in scenes if s.ko and not s.en]
    if missing:
        for s, en in zip(missing, agents.translate_prompts(llm, [s.ko for s in missing])):
            s.en = en
    for s in scenes:  # 그림 설명에 이름이 나오는 인물도 참고 이미지로
        s.people += [n for n, _ in plan.characters if n in s.ko and n not in s.people]
    chars = [(n, d.split(" (변화:")[0]) for n, d in plan.characters]
    looks = agents.character_sheets(llm, chars) if chars else []
    title = next((line[2:] for line in plan.text.split("\n## 제목 후보")[-1].split("\n") if line.startswith("- ")), "")
    return KlingSheet(content_id, title, [(n, d, en) for (n, d), en in zip(chars, looks)], scenes)


def _clock(sec: float) -> str:
    return f"약 {round(sec)}초" if sec < 90 else f"약 {sec / 60:.1f}분"


def worksheet_md(sheet: KlingSheet) -> str:
    total = sum(s.seconds for s in sheet.scenes)
    out = [f"# Kling 작업지 · {sheet.content_id}", "", f"**{sheet.title}**", "",
           f"- 장면 {len(sheet.scenes)}개 · 영상 {total / 60:.0f}분 · 그림 비율 **16:9**",
           "- 순서: ① 인물 기준 이미지 → ② 장면 그림 (인물이 나오는 장면은 그 인물 기준 이미지를 참고 이미지로)",
           "- 받은 그림은 **파일 이름 그대로**(`01.png` …) Drive 자료 폴더에 올리기. `출처.txt` 는 함께 두기.",
           "- 코드 블록 오른쪽 위 복사 버튼으로 영어 프롬프트를 그대로 붙여 넣기.", ""]
    if sheet.characters:
        out += ["## ① 인물 기준 이미지", ""]
        for name, desc, en in sheet.characters:
            out += [f"### {name}", f"- {desc}", "", "```text", en or "(프롬프트 없음 — 한국어 설명을 보고 직접)", "```", ""]
    out += ["## ② 장면 그림", ""]
    for s in sheet.scenes:
        out += [f"### {s.number:02}.png — {s.title}  ({_clock(s.seconds)})"]
        if s.people:
            out.append(f"- 참고 이미지: {', '.join(s.people)}")
        out += [f"- 한국어: {s.ko}", "", "```text", s.en or s.ko, "```", ""]
    out += ["## ③ 올리기", "", "- 장면 그림을 모두 Drive 자료 폴더에 `NN.png` 로 올림 → Notion status 가 APPROVED 인지 확인 → Actions `render` 실행"]
    return "\n".join(out) + "\n"


def prompts_csv(sheet: KlingSheet) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "scene", "seconds", "people", "prompt_en", "prompt_ko"])
    for s in sheet.scenes:
        w.writerow([f"{s.number:02}.png", s.title, round(s.seconds), " ".join(s.people), s.en, s.ko])
    return buf.getvalue()


def link_bullet(text: str, url: str) -> dict:
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
        {"type": "text", "text": {"content": text, "link": {"url": url}}}]}}


def info_callout_id(blocks: list[dict]) -> str | None:
    """구분선 바로 뒤 📌 대본 정보 콜아웃."""
    for a, b in zip(blocks, blocks[1:]):
        if a.get("type") == "divider" and b.get("type") == "callout" and plain(b).startswith("대본 정보"):
            return b["id"]
    return None


def write_files(sheet: KlingSheet, folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    files = {"작업지.md": worksheet_md(sheet), "prompts.csv": "\ufeff" + prompts_csv(sheet),  # 엑셀 한글용 BOM
             "출처.txt": SOURCE_LINE + "\n"}
    paths = []
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8", newline="")  # 줄바꿈을 바꾸지 않음 (csv 빈 줄 방지)
        paths.append(folder / name)
    return paths
