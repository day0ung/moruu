import logging
from dataclasses import replace
from datetime import datetime

from channels.llm.client import LLMError, LLMQuotaError
from core.models import KST, Post
from core.notion_store import Table
from pipelines.ai_story.__main__ import run_plan, run_write
from pipelines.ai_story.doc import plain, plan_blocks
from test_story_doc import PLAN, as_read

LOG = logging.getLogger("test")
POST = Post("page-1", "YT-롱폼-1", "", "", None, "", None, series="s1", channel="YT-롱폼")


class Store:
    """블록을 메모리에 쌓는 가짜 Notion (자식·after 지원)."""

    def __init__(self, posts=(POST,)):
        self.posts = list(posts)
        self.blocks: dict[str, list[dict]] = {"s1": []}
        self._n = 0
        self._put("page-1", plan_blocks(PLAN))
        self.created, self.child_pages, self.rows, self.failed, self.written = [], [], [], [], []

    def _put(self, parent, children, after=None):
        made = []
        for b in children:
            self._n += 1
            bid = f"b{self._n}"
            made.append(as_read(b, bid))
            kids = b[b["type"]].get("children") or []
            if kids:
                self._put(bid, kids)
        lst = self.blocks.setdefault(parent, [])
        at = next((i + 1 for i, b in enumerate(lst) if b["id"] == after), len(lst)) if after else len(lst)
        lst[at:at] = made
        return made

    def find_series(self, name):
        return "s1" if name == "야담" else None

    def page_blocks(self, page_id):
        return list(self.blocks.get(page_id, []))

    def tables(self, page_id):
        return [Table("tb", [["인물", "목소리", "나이·성격"], ["내레이션", "C", ""]], True)]

    def series_episodes(self, sid):
        return []

    def create_page(self, props, children):
        self.created.append(props)
        pid = f"new{len(self.created)}"
        self._put(pid, children)
        return pid

    def create_child_page(self, parent, title, children):
        self.child_pages.append((parent, title, children))
        return "cmp"

    def append_blocks(self, block_id, children, after=None):
        return self._put(block_id, children, after)

    def add_table_rows(self, table_id, rows):
        self.rows += rows

    def approved_plans(self):
        return list(self.posts)

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def mark_written(self, post, summary):
        self.written.append((post.content_id, summary))


def chapter_reply(chars):
    per = chars // 3
    return {"scenes": [{"title": f"s{i}", "music": "", "lines": [{"speaker": "내레이션", "text": "가" * (per - 4)},
                                                                   {"speaker": "사또", "text": "게 섰거라"}]}
                       for i in range(3)]}


class FakeLLM:
    def __init__(self, quota_after=None):
        self.calls, self.quota_after = [], quota_after

    def chat_json(self, messages, role):
        self.calls.append(role)
        if self.quota_after is not None and len(self.calls) > self.quota_after:
            raise LLMQuotaError("429")
        if role == "write":
            return chapter_reply(1032 if "챕터 1 /" in messages[-1]["content"] else 903)  # 4분·3.5분
        return {"plan": {"plans": [PLAN, PLAN, PLAN]}, "review": {"verdict": "PASS"},
                "light": {"prompts": [{"ko": "그림", "en": "picture"}] * 3, "summary": "갈등: 부채"}}[role]


def types(store, pid="page-1"):
    return [b["type"] for b in store.blocks[pid]]


def test_plan_creates_pages_and_compare_table():
    store, sent = Store(), []
    now = datetime(2026, 10, 31, 9, 5, tzinfo=KST)
    assert run_plan(store, FakeLLM(), "야담", "부채", LOG, sent.append, now, compare_parent="work") == 0
    assert len(store.created) == 3
    assert store.created[0]["content_id"] == {"title": [{"text": {"content": "YT-롱폼-20261031-0905-1"}}]}
    assert store.created[0]["status"] == {"select": {"name": "기획"}}
    parent, title, children = store.child_pages[0]
    assert parent == "work" and title == "🗳 기획 비교 · 야담 · 10/31 09:05"
    rows = children[1]["table"]["children"]
    assert [plain(as_read(r, "r")).split(" | ")[0] for r in rows] == \
        ["항목", "제목", "로그라인", "시청 포인트", "반전", "오프닝", "열기"]
    assert rows[-1]["table_row"]["cells"][1][0]["text"]["link"]["url"] == "https://www.notion.so/new1"
    assert sent[0].startswith("📝 기획안 3개 · 야담")


def test_plan_errors():
    assert run_plan(Store(), FakeLLM(), "없음", "", LOG, print, datetime.now(KST)) == 1

    class Broken(FakeLLM):
        def chat_json(self, messages, role):
            raise LLMError("gemini/x: 403 free tier is not available")

    sent = []
    assert run_plan(Store(), Broken(), "야담", "", LOG, sent.append, datetime.now(KST)) == 1
    assert sent == ["❌ 기획 실패 · 야담: gemini/x: 403 free tier is not available"]


def test_write_full_episode_layout():
    store, sent = Store(), []
    assert run_write(store, FakeLLM(), LOG, sent.append) == 0
    kinds = types(store)
    end = kinds.index("divider")
    assert kinds[end + 1] == "callout"  # 대본 정보·목차가 기획 구역 바로 뒤
    info = store.blocks[store.blocks["page-1"][end + 1]["id"]]
    assert [plain(b) for b in info] == ["00:00  챕터 1 · 주막", "04:00  챕터 2 · 관아"]
    assert kinds.count("heading_1") == 2 and kinds.count("heading_2") == 6 and kinds[-1] == "toggle"  # 그림 목록이 맨 끝
    images = [plain(b) for b in store.blocks[store.blocks["page-1"][-1]["id"]]]
    assert images[0] == "01.png — 그림\nEN: picture" and images[-1] == "06.png — 그림\nEN: picture"
    assert store.rows == [["사또", "ko-KR-Neural2-C", "50대 남성 (변화: 깨달음)"]]  # 새 인물 → 바이블
    assert store.written == [("YT-롱폼-1", "갈등: 부채")]
    assert sent[0].startswith("✍️ YT-롱폼-1 대본 DRAFT · 챕터 2개 새로 씀")


def test_after_write_hook_and_its_failure_does_not_fail_the_script():
    store, sent, seen = Store(), [], []
    assert run_write(store, FakeLLM(), LOG, sent.append, after_write=lambda p: seen.append(p.content_id) or "drive/x") == 0
    assert seen == ["YT-롱폼-1"] and "Kling 작업지 drive/x" in sent[0]

    def boom(post):
        raise ValueError("no")

    store, sent = Store(), []
    assert run_write(store, FakeLLM(), LOG, sent.append, after_write=boom) == 0
    assert store.written and "Kling" not in sent[0]


def test_quota_pauses_and_next_run_resumes():
    store, sent = Store(), []
    assert run_write(store, FakeLLM(quota_after=3), LOG, sent.append) == 1  # 챕터 1 (write·review·light) 뒤 한도
    assert sent[0].startswith("⏸ YT-롱폼-1") and store.failed == [] and store.written == []
    assert types(store).count("heading_1") == 1

    llm = FakeLLM()
    assert run_write(store, llm, LOG, sent.append) == 0
    assert llm.calls == ["write", "review", "light", "light"]  # 챕터 2 + 요약만
    heads = [plain(b) for b in store.blocks["page-1"] if b["type"] == "heading_2"]
    assert heads[3] == "장면 4 · s0"


def test_missing_series_or_plan_marks_failed():
    store = Store([replace(POST, series="")])
    assert run_write(store, FakeLLM(), LOG, print) == 1
    assert store.failed == [("YT-롱폼-1", "story: 시리즈 연결 없음")]
    store = Store()
    store.blocks["page-1"] = []
    assert run_write(store, FakeLLM(), LOG, print) == 1
    assert store.failed[0][1].startswith("story: 기획 구역에 '챕터 N · 제목' 토글이 없음")
