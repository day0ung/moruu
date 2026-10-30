import csv
import io
import logging

from pipelines.ai_story import export
from pipelines.ai_story.__main__ import export_episode
from pipelines.ai_story.doc import chapter_blocks, info_blocks
from test_story_pipeline import POST, Store

LOG = logging.getLogger("test")


def scene(title, lines, ko="", en=""):
    return {"title": title, "music": "", "image_prompt": ko, "image_prompt_en": en,
            "lines": [{"speaker": w, "text": t} for w, t in lines]}


def episode_store():
    store = Store()
    blocks = chapter_blocks(1, "주막", [
        scene("주막", [("내레이션", "가" * 258), ("사또", "게 섰거라")], "사또가 주막 마당에 섬", "magistrate in an inn yard"),
        scene("고개", [("내레이션", "나" * 129)], "고갯길의 사또 그림자", ""),
    ], 1, "챕터 1: PASS")
    end = next(b["id"] for b in store.blocks["page-1"] if b["type"] == "divider")
    store.append_blocks("page-1", blocks)
    store.append_blocks("page-1", info_blocks([(1, "주막", 400)], 400, 258, []), after=end)
    return store


class LLM:
    def __init__(self):
        self.calls = []

    def chat_json(self, messages, role):
        text = messages[-1]["content"]
        self.calls.append(text[:20])
        if "영어 프롬프트로 옮기세요" in text:
            return {"prompts": ["mountain pass"]}
        return {"prompts": ["old magistrate reference"]}


def test_read_scenes_seconds_people_and_images():
    store = episode_store()
    scenes = export.read_scenes(store, store.page_blocks("page-1"))
    assert [(s.number, s.title, s.people, s.ko, s.en) for s in scenes] == [
        (1, "주막", ["사또"], "사또가 주막 마당에 섬", "magistrate in an inn yard"),
        (2, "고개", [], "고갯길의 사또 그림자", ""),
    ]
    assert round(scenes[0].seconds) == 61 and round(scenes[1].seconds) == 30  # 258+4자 → 약 1분, 129자 → 30초


def test_build_sheet_translates_missing_and_makes_character_refs():
    store, llm = episode_store(), LLM()
    sheet = export.build_sheet(store, llm, "YT-롱폼-1", "page-1")
    assert [s.en for s in sheet.scenes] == ["magistrate in an inn yard", "mountain pass"]
    assert sheet.scenes[1].people == ["사또"]  # 그림 설명에 이름이 나오면 참고 이미지로
    assert sheet.characters == [("사또", "50대 남성", "old magistrate reference")]
    assert sheet.title == "제목1"


def test_files(tmp_path):
    sheet = export.build_sheet(episode_store(), LLM(), "YT-롱폼-1", "page-1")
    paths = export.write_files(sheet, tmp_path)
    assert [p.name for p in paths] == ["작업지.md", "prompts.csv", "출처.txt"]
    md = (tmp_path / "작업지.md").read_text(encoding="utf-8")
    assert "## ① 인물 기준 이미지" in md and "### 01.png — 주막  (약 61초)" in md
    assert "- 참고 이미지: 사또" in md and "```text\nmagistrate in an inn yard\n```" in md
    rows = list(csv.reader(io.StringIO((tmp_path / "prompts.csv").read_text(encoding="utf-8-sig"))))
    assert rows[0] == ["file", "scene", "seconds", "people", "prompt_en", "prompt_ko"]
    assert rows[2][:2] == ["02.png", "고개"]
    assert (tmp_path / "출처.txt").read_text(encoding="utf-8") == "AI 생성 이미지: Kling\n"


def test_export_episode_uploads_and_links(tmp_path):
    store = episode_store()
    uploaded = []
    where = export_episode(store, LLM(), POST, LOG, out=tmp_path,
                           uploader=lambda cid, paths: uploaded.append((cid, [p.name for p in paths])) or "https://drive/f")
    assert where == "https://drive/f" and uploaded == [("YT-롱폼-1", ["작업지.md", "prompts.csv", "출처.txt"])]
    info = export.info_callout_id(store.page_blocks("page-1"))
    link = store.page_blocks(info)[-1]
    assert link["bulleted_list_item"]["rich_text"][0]["plain_text"] == "📥 Kling 작업지 (Drive)"


def test_export_episode_local_only(tmp_path):
    where = export_episode(episode_store(), LLM(), POST, LOG, out=tmp_path)
    assert where.endswith("작업지.md") and (tmp_path / "YT-롱폼-1" / "prompts.csv").is_file()
