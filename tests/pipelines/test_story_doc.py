from pipelines.ai_drama.script import parse_episode
from pipelines.ai_story.doc import (CHAPTER_TOGGLE, chapter_blocks, chapter_toggles, image_line, info_blocks,
                                    is_image_line, line_text, parse_image_line, plain, plan_blocks, read_plan,
                                    split_speaker, written)

PLAN = {
    "titles": ["제목1", "제목2"], "thumbnail": "썸네일", "logline": "로그라인", "hook": "궁금증", "opening": "옛날 옛적에",
    "synopsis": "줄거리", "characters": [{"name": "사또", "desc": "50대 남성", "arc": "깨달음"}],
    "chapters": [{"title": "주막", "minutes": 4, "event": "만남", "emotion": "의심", "foreshadow": "부채",
                  "scenes": ["주막 — 나그네 등장", "마당 — 부채를 떨어뜨림"]},
                 {"title": "관아", "minutes": 3.5, "event": "재판", "emotion": "긴장", "foreshadow": "회수",
                  "scenes": ["관아 — 재판"]}],
    "twist": "부채의 주인",
}


def as_read(block, bid):
    """Notion 이 돌려주는 모양 (plain_text, children 없음)."""
    kind = block["type"]
    body = {k: v for k, v in block[kind].items() if k != "children"}
    if "rich_text" in body:
        body["rich_text"] = [{"plain_text": r["text"]["content"]} for r in body["rich_text"]]
    if kind == "table_row":
        body["cells"] = [[{"plain_text": r["text"]["content"]} for r in c] for c in body["cells"]]
    return {"type": kind, kind: body, "id": bid}


def stored(blocks):
    """블록 목록 → (맨 위 읽기 결과, 자식 읽기 함수)."""
    top, kids = [], {}
    for i, b in enumerate(blocks):
        top.append(as_read(b, f"b{i}"))
        children = b[b["type"]].get("children") or []
        kids[f"b{i}"] = [as_read(c, f"b{i}-{j}") for j, c in enumerate(children)]
    return top, lambda bid: kids.get(bid, [])


def test_plan_has_no_paragraph_or_heading2_and_ends_with_divider():
    blocks = plan_blocks(PLAN)
    kinds = [b["type"] for b in blocks]
    assert "paragraph" not in kinds and "heading_2" not in kinds and kinds[-1] == "divider"
    top, _ = stored(blocks)
    assert parse_episode(top, {"내레이션"}) == ([], [])  # 렌더가 기획 구역을 대본으로 읽지 않음


def test_plan_roundtrip():
    top, children = stored(plan_blocks(PLAN))
    plan = read_plan(top, children)
    assert plan.chapters == [("주막", "주막 — 나그네 등장\n마당 — 부채를 떨어뜨림"), ("관아", "관아 — 재판")]
    assert plan.minutes == [4.0, 3.5]
    assert plan.characters == [("사또", "50대 남성 (변화: 깨달음)")]
    assert plan.end_id == top[-1]["id"]
    assert "옛날 옛적에" in plan.text and "1 | 4 | 만남 | 의심 | 부채" in plan.text and "### 챕터 1 · 주막 (약 4분)" in plan.text


def test_read_plan_stops_at_script():
    top, children = stored(plan_blocks(PLAN)[:-1] + chapter_blocks(1, "x", [], 1))  # 구분선 없이 바로 대본
    assert len(read_plan(top, children).chapters) == 2


def test_line_text():
    assert line_text({"speaker": "내레이션", "text": "그날 저녁"}) == "그날 저녁"
    assert line_text({"speaker": "사또", "emotion": "노하여", "text": "네 이놈"}) == "사또(노하여): 네 이놈"


def test_chapter_blocks_render_format_and_images_folded():
    scenes = [{"title": "주막", "music": "잔잔", "image_prompt": "주막 마당",
               "lines": [{"speaker": "내레이션", "text": "그날 밤."}, {"speaker": "사또", "text": "게 누구냐."}]},
              {"title": "관아", "music": "", "lines": [{"speaker": "내레이션", "text": "아침."}]}]
    blocks = chapter_blocks(2, "관아", scenes, first_scene=5, note="챕터 2: PASS")
    assert [b["type"] for b in blocks] == ["heading_1", "toggle", "heading_2", "paragraph", "heading_2", "paragraph"]
    folded = [plain(as_read(c, "c")) for c in blocks[1]["toggle"]["children"]]
    assert folded == ["챕터 2: PASS", "05.png — 주막 마당"] and is_image_line(folded[1])
    parsed, problems = parse_episode([as_read(b, str(i)) for i, b in enumerate(blocks)], {"내레이션", "사또"})
    assert problems == [] and [s.title for s in parsed] == ["장면 5 · 주막", "장면 6 · 관아"]


def test_image_line_roundtrip_and_split_speaker():
    assert parse_image_line(image_line(7, "주막 마당", "an inn yard")) == (7, "주막 마당", "an inn yard")
    assert parse_image_line(image_line(12, "고개")) == (12, "고개", "")
    assert parse_image_line("메모") is None
    assert split_speaker("사또(노하여): 네 이놈") == ("사또", "네 이놈")
    assert split_speaker("그날 밤, 바람이 불었다.") == (None, "그날 밤, 바람이 불었다.")


def test_written_and_chapter_toggles():
    top = [as_read(b, f"x{i}") for i, b in enumerate(chapter_blocks(1, "a", [{"title": "s", "lines": []}] * 3, 1))]
    assert written(top) == (1, 4)
    assert chapter_toggles(top) == [(1, "a", "x1")] and plain(top[1]) == CHAPTER_TOGGLE


def test_info_blocks_toc_times():
    [info] = info_blocks([(1, "주막", 1032), (2, "관아", 516)], 1548, 258, ["챕터 1: PASS", "⚠ 챕터 2: 검수 미통과"])
    assert plain(as_read(info, "i")) == "대본 정보 · 약 6분 · 1,548자 · 챕터 2개 · 검수 미통과 1개"
    lines = [plain(as_read(c, "c")) for c in info["callout"]["children"]]
    assert lines == ["00:00  챕터 1 · 주막", "04:00  챕터 2 · 관아", "⚠ 챕터 2: 검수 미통과"]
