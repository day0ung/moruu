import json
from datetime import datetime

import httpx

from core.models import KST, Post
from core.notion_store import API, DbIds, NotionStore

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=KST)


def make_store(responses):
    """responses: 요청 순서대로 돌려줄 JSON 목록. 보낸 요청은 store.sent 에 쌓인다."""
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append((req.method, req.url.path, json.loads(req.content or b"{}"), req.headers))
        return httpx.Response(200, json=responses.pop(0) if responses else {})

    http = httpx.Client(base_url=API, transport=httpx.MockTransport(handler))
    store = NotionStore("ntn-token", DbIds("db-c", "db-m", "db-f"), http=http)
    return store, sent


def page(pid, cid):
    return {
        "id": pid,
        "properties": {
            "content_id": {"title": [{"plain_text": cid}]},
            "본문": {"rich_text": [{"plain_text": "본문"}]},
            "status": {"select": {"name": "APPROVED"}},
        },
    }


def post():
    return Post("page-1", "TH-1", "수익", "본문", None, "", None)


def test_approved_due_filters_and_paginates():
    store, sent = make_store([
        {"results": [page("p1", "TH-1")], "has_more": True, "next_cursor": "c2"},
        {"results": [page("p2", "TH-2")], "has_more": False},
    ])
    posts = store.approved_threads_due(NOW)
    assert [p.content_id for p in posts] == ["TH-1", "TH-2"]
    method, path, body, headers = sent[0]
    assert (method, path) == ("POST", "/v1/databases/db-c/query")
    assert headers["Authorization"] == "Bearer ntn-token"
    assert headers["Notion-Version"] == "2022-06-28"
    conds = body["filter"]["and"]
    assert {"property": "status", "select": {"equals": "APPROVED"}} in conds
    assert {"property": "채널", "select": {"equals": "Threads"}} in conds
    assert {"property": "예약시각", "date": {"on_or_before": NOW.isoformat()}} in conds
    assert sent[1][2]["start_cursor"] == "c2"


def test_mark_posted_sets_status_ids_time():
    store, sent = make_store([{}])
    store.mark_posted(post(), "m1", "r1", NOW)
    method, path, body, _ = sent[0]
    assert (method, path) == ("PATCH", "/v1/pages/page-1")
    props = body["properties"]
    assert props["status"] == {"select": {"name": "POSTED"}}
    assert props["게시ID"]["rich_text"][0]["text"]["content"] == "m1"
    assert props["댓글ID"]["rich_text"][0]["text"]["content"] == "r1"
    assert props["게시시각"] == {"date": {"start": NOW.isoformat()}}


def test_mark_posting_sets_status_posting():
    store, sent = make_store([{}])
    store.mark_posting(post())
    method, path, body, _ = sent[0]
    assert (method, path) == ("PATCH", "/v1/pages/page-1")
    assert body["properties"] == {"status": {"select": {"name": "POSTING"}}}


def test_mark_approved_restores_status():
    store, sent = make_store([{}])
    store.mark_approved(post())
    method, path, body, _ = sent[0]
    assert (method, path) == ("PATCH", "/v1/pages/page-1")
    assert body["properties"] == {"status": {"select": {"name": "APPROVED"}}}


def test_add_metrics_creates_row_in_metrics_db():
    store, sent = make_store([{}])
    store.add_metrics(post(), 24, 30.5, {"views": 120, "likes": 4, "unknown": 9}, NOW)
    _, path, body, _ = sent[0]
    assert path == "/v1/pages"
    assert body["parent"] == {"database_id": "db-m"}
    props = body["properties"]
    assert props["경과"] == {"select": {"name": "24h"}}
    assert props["실제경과h"] == {"number": 30.5}
    assert props["조회"] == {"number": 120}
    assert "unknown" not in json.dumps(props)


def test_mark_collected_sets_checkboxes():
    store, sent = make_store([{}])
    store.mark_collected(post(), [24, 72])
    props = sent[0][2]["properties"]
    assert props == {"수집_24h": {"checkbox": True}, "수집_72h": {"checkbox": True}}


def test_log_failure_goes_to_failures_db():
    store, sent = make_store([{}])
    store.log_failure("TH-1", "post", "1", "boom", 2, "FAILED", NOW)
    body = sent[0][2]
    assert body["parent"] == {"database_id": "db-f"}
    assert body["properties"]["step"] == {"select": {"name": "post"}}
    assert body["properties"]["retry_count"] == {"number": 2}
