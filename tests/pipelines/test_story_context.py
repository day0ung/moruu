from core.models import Post
from core.notion_store import Table
from pipelines.ai_story.checks import chapter_problems, chapter_target, spoken_chars
from pipelines.ai_story.context import load_series


def blk(kind, text):
    return {"type": kind, kind: {"rich_text": [{"plain_text": text}]}}


class Store:
    def page_blocks(self, page_id):
        return [blk("paragraph", "인물 바이블 설명"), blk("heading_2", "세계관"), blk("paragraph", "1990년대 지방 소도시"),
                blk("bulleted_list_item", "시어머니는 존댓말을 섞음"), blk("heading_2", "금지·주의"),
                blk("paragraph", "실존 기업 금지"), blk("heading_2", "인물")]

    def tables(self, page_id):
        return [Table("tb", [["인물", "목소리", "나이·성격", "그림 설명"], ["내레이션", "A", "", ""],
                             ["시어머니", "A", "60대 후반", "회색 단발"]], True)]

    def series_episodes(self, series_id):
        return [Post("e1", "YT-1", "", "", None, "", None, summary="상속 갈등, 화해"),
                Post("e2", "YT-2", "", "", None, "", None, summary=""),
                Post("me", "YT-3", "", "", None, "", None, summary="지금 쓰는 회차")]


def test_load_series():
    s = load_series(Store(), "s1", exclude_page="me")
    assert s.world == "1990년대 지방 소도시\n- 시어머니는 존댓말을 섞음" and s.rules == "실존 기업 금지"
    assert s.names == {"내레이션", "시어머니"} and s.table_id == "tb"
    assert s.cast_text() == "- 시어머니: 60대 후반 / 외형: 회색 단발"
    assert s.episodes_text() == "1. 상속 갈등, 화해"


def test_new_rows_guess_voice_in_header_order():
    s = load_series(Store(), "s1")
    rows = s.new_rows([("시어머니", "있음"), ("변호사", "50대 남성, 침착함"), ("딸", "30대")])
    assert rows == [["변호사", "ko-KR-Neural2-C", "50대 남성, 침착함", ""], ["딸", "ko-KR-Neural2-A", "30대", ""]]
    assert "변호사" in s.names


def scene(*lines):
    return {"title": "t", "lines": [{"speaker": w, "text": t} for w, t in lines]}


def test_chapter_problems():
    speakers = {"내레이션", "아들"}
    good = [scene(("내레이션", "가" * 400), ("아들", "네")), scene(("내레이션", "나" * 400))]
    assert chapter_problems(good, speakers, target=800) == []
    bad = [scene(("며느리", "어머니"), ("내레이션", "결론: 끝"), ("아들", "최고 [쉬 1]"))]
    assert chapter_problems(bad, speakers, target=800) == [
        "장면 수 1개 — 3~8개로",
        "장면 1: '며느리' 는 인물 목록에 없음 — 내레이션, 아들 중에서",
        "장면 1: 내레이션이 '이름:' 으로 시작함 — 문장을 바꿀 것: 결론: 끝",
        "장면 1: 대괄호 [ ] 는 [쉼 0.5] 만 — 오타 확인",
        "장면 1: 금지어 '최고'",
        "분량 13자 — 목표 800자 (±40%)",
    ]


def test_targets():
    assert chapter_target(30, 8) == 968
    assert spoken_chars([scene(("내레이션", "가 나"))]) == 2
