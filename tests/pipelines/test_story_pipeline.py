import logging
from dataclasses import replace
from datetime import datetime

from channels.llm.client import LLMQuotaError
from core.models import KST, Post
from core.notion_store import Table
from pipelines.ai_story.__main__ import run_plan, run_write
from pipelines.ai_story.doc import PLAN_TOGGLE, plan_blocks

LOG = logging.getLogger("test")
POST = Post("page-1", "YT-롱폼-1", "", "", None, "", None, series="s1", channel="YT-롱폼")
PLAN = {"titles": ["엄마의 통장"], "thumbnail": "t", "synopsis": "줄거리",
        "characters": [{"name": "변호사", "desc": "50대 남성"}],
        "chapters": [{"title": "저녁", "beats": ["사건"]}, {"title": "편지", "beats": ["반전"]}], "twist": "x"}


def as_read(block, bid):
    kind = block["type"]
    body = {k: v for k, v in block[kind].items() if k != "children"}
    body["rich_text"] = [{"plain_text": r["text"]["content"]} for r in body["rich_text"]]
    return {"type": kind, kind: body, "id": bid}


class Store:
    """페이지 블록을 메모리에 쌓는 가짜 Notion."""

    def __init__(self, posts=(POST,)):
        self.posts = list(posts)
        [plan_toggle] = plan_blocks(PLAN)
        self.blocks = {"page-1": [as_read(plan_toggle, "plan")],
                       "plan": [as_read(b, f"p{i}") for i, b in enumerate(plan_toggle["toggle"]["children"])],
                       "s1": [], "review": []}
        self.created, self.rows, self.failed, self.written = [], [], [], []

    def find_series(self, name):
        return "s1" if name == "시험 시리즈" else None

    def page_blocks(self, page_id):
        return list(self.blocks.get(page_id, []))

    def tables(self, page_id):
        return [Table("tb", [["인물", "목소리", "나이·성격"], ["내레이션", "A", ""], ["아들", "C", "30대"]], True)]

    def series_episodes(self, sid):
        return []

    def create_page(self, props, children):
        self.created.append((props, children))
        return f"new{len(self.created)}"

    def append_blocks(self, block_id, children):
        made = []
        for i, b in enumerate(children):
            bid = "review" if b["type"] == "toggle" else f"{block_id}-{len(self.blocks.get(block_id, []))}-{i}"
            made.append(as_read(b, bid))
        self.blocks.setdefault(block_id, []).extend(made)
        return made

    def add_table_rows(self, table_id, rows):
        self.rows += rows

    def approved_plans(self):
        return list(self.posts)

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def mark_written(self, post, summary):
        self.written.append((post.content_id, summary))


def chapter_reply(n_scenes=3):
    return {"scenes": [{"title": f"s{i}", "music": "", "lines": [{"speaker": "내레이션", "text": "가" * 330},
                                                                   {"speaker": "변호사", "text": "네."}]}
                       for i in range(n_scenes)]}


class FakeLLM:
    def __init__(self, quota_after=None):
        self.calls, self.quota_after = [], quota_after

    def chat_json(self, messages, role):
        self.calls.append(role)
        if self.quota_after is not None and len(self.calls) > self.quota_after:
            raise LLMQuotaError("429")
        return {"plan": {"plans": [PLAN, PLAN, PLAN]}, "write": chapter_reply(), "review": {"verdict": "PASS"},
                "light": {"prompts": ["그림"] * 3, "summary": "갈등: 상속"}}[role]


def test_plan_creates_three_pages():
    store, sent = Store(), []
    now = datetime(2026, 10, 31, 9, 5, tzinfo=KST)
    assert run_plan(store, FakeLLM(), "시험 시리즈", "상속", LOG, sent.append, now) == 0
    assert len(store.created) == 3
    props, children = store.created[0]
    assert props["content_id"] == {"title": [{"text": {"content": "YT-롱폼-20261031-0905-1"}}]}
    assert props["status"] == {"select": {"name": "기획"}} and props["시리즈"] == {"relation": [{"id": "s1"}]}
    assert children[0]["type"] == "toggle"
    assert sent[0].startswith("📝 기획안 3개 · 시험 시리즈")


def test_plan_unknown_series():
    assert run_plan(Store(), FakeLLM(), "없음", "", LOG, print, datetime.now(KST)) == 1


def test_write_full_episode():
    store, sent, llm = Store(), [], FakeLLM()
    assert run_write(store, llm, LOG, sent.append, minutes=8) == 0
    page = store.blocks["page-1"]
    kinds = [b["type"] for b in page]
    assert kinds.count("heading_1") == 2 and kinds.count("heading_2") == 6 and kinds.count("callout") == 6
    heads = [b["heading_2"]["rich_text"][0]["plain_text"] for b in page if b["type"] == "heading_2"]
    assert heads[0] == "장면 1 · s0" and heads[3] == "장면 4 · s0"  # 장면 번호가 챕터를 넘어 이어짐
    assert store.rows == [["변호사", "ko-KR-Neural2-C", "50대 남성"]]  # 새 인물 → 바이블
    assert [b["paragraph"]["rich_text"][0]["plain_text"].split(" ·")[0] for b in store.blocks["review"]] == \
        ["챕터 1: PASS (수정 0회)", "챕터 2: PASS (수정 0회)"]
    assert store.written == [("YT-롱폼-1", "갈등: 상속")]
    assert sent[0].startswith("✍️ YT-롱폼-1 대본 DRAFT · 챕터 2개 새로 씀")


def test_quota_pauses_and_next_run_resumes():
    store, sent = Store(), []
    # 챕터 1: write, review, light(그림) = 3 호출 → 4번째(챕터 2 작성)에서 한도
    assert run_write(store, FakeLLM(quota_after=3), LOG, sent.append, minutes=8) == 1
    assert sent[0].startswith("⏸ YT-롱폼-1") and store.failed == [] and store.written == []
    assert sum(b["type"] == "heading_1" for b in store.blocks["page-1"]) == 1

    llm = FakeLLM()
    assert run_write(store, llm, LOG, sent.append, minutes=8) == 0
    assert llm.calls == ["write", "review", "light", "light"]  # 챕터 2 + 요약만
    heads = [b["heading_2"]["rich_text"][0]["plain_text"] for b in store.blocks["page-1"] if b["type"] == "heading_2"]
    assert heads[3] == "장면 4 · s0"
    assert len(store.blocks["review"]) == 2  # 검수 기록 토글 재사용


def test_missing_series_or_plan_marks_failed():
    store = Store([replace(POST, series="")])
    assert run_write(store, FakeLLM(), LOG, print) == 1
    assert store.failed == [("YT-롱폼-1", "story: 시리즈 연결 없음")]
    store = Store()
    store.blocks["page-1"] = []
    assert run_write(store, FakeLLM(), LOG, print) == 1
    assert store.failed == [("YT-롱폼-1", f"story: '{PLAN_TOGGLE}' 토글 없음")]
