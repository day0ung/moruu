from pipelines.ai_drama.script import parse_episode
from pipelines.ai_story.doc import (PLAN_TOGGLE, chapter_blocks, find_toggle, line_text, plan_blocks, plain,
                                    read_plan, written)

PLAN = {
    "titles": ["제목1", "제목2"], "thumbnail": "엄마가 숨긴 통장", "synopsis": "줄거리",
    "characters": [{"name": "시어머니", "desc": "60대 후반"}, {"name": "변호사", "desc": "50대 남성"}],
    "chapters": [{"title": "저녁 식탁", "beats": ["사건", "복선"]}, {"title": "편지", "beats": ["반전"]}],
    "twist": "통장의 주인",
}


def as_read(block):
    """Notion 이 돌려주는 모양 (plain_text) 으로."""
    kind = block["type"]
    body = dict(block[kind])
    body["rich_text"] = [{"plain_text": r["text"]["content"]} for r in body["rich_text"]]
    return {"type": kind, kind: body, "id": "x"}


def test_plan_roundtrip_through_toggle():
    [toggle] = plan_blocks(PLAN)
    assert plain(toggle) == PLAN_TOGGLE
    plan = read_plan([as_read(b) for b in toggle["toggle"]["children"]])
    assert plan.chapters == [("저녁 식탁", "사건\n복선"), ("편지", "반전")]
    assert plan.characters == [("시어머니", "60대 후반"), ("변호사", "50대 남성")]
    assert "## 시놉시스\n줄거리" in plan.text and "- 제목1" in plan.text


def test_line_text():
    assert line_text({"speaker": "내레이션", "text": "그날 저녁"}) == "그날 저녁"
    assert line_text({"speaker": "아들", "emotion": "서운하게", "text": "네"}) == "아들(서운하게): 네"
    assert line_text({"speaker": "아들", "emotion": "", "text": "네"}) == "아들: 네"


def test_chapter_blocks_render_format_parses():
    scenes = [{"title": "저녁 식탁", "music": "잔잔", "image_prompt": "60대 여성, 거실",
               "lines": [{"speaker": "내레이션", "text": "그날 저녁."}, {"speaker": "아들", "emotion": "", "text": "네."}]},
              {"title": "다음 날", "music": "", "lines": [{"speaker": "내레이션", "text": "아침."}]}]
    blocks = chapter_blocks(2, "편지", scenes, first_scene=5)
    assert [b["type"] for b in blocks] == ["heading_1", "heading_2", "callout", "paragraph", "heading_2", "paragraph"]
    assert plain(blocks[2]) == "05.png — 60대 여성, 거실"
    parsed, problems = parse_episode([as_read(b) for b in blocks], {"내레이션", "아들"})
    assert problems == []
    assert [(s.title, s.music, len(s.lines)) for s in parsed] == [("장면 5 · 저녁 식탁", "잔잔", 2), ("장면 6 · 다음 날", "잔잔", 1)]


def test_long_scene_splits_paragraphs():
    lines = [{"speaker": "내레이션", "text": "가" * 500} for _ in range(8)]
    blocks = chapter_blocks(1, "t", [{"title": "s", "lines": lines}], 1)
    paras = [b for b in blocks if b["type"] == "paragraph"]
    assert len(paras) >= 3 and all(len(plain(p)) <= 1800 for p in paras)


def test_written_and_find_toggle():
    blocks = [as_read(b) for b in chapter_blocks(1, "a", [{"title": "s", "lines": []}] * 3, 1)]
    blocks += [{"type": "toggle", "id": "tg", "toggle": {"rich_text": [{"plain_text": PLAN_TOGGLE}]}}]
    assert written(blocks) == (1, 4)
    assert find_toggle(blocks, PLAN_TOGGLE) == "tg" and find_toggle(blocks, "없음") is None
