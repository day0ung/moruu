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


def test_approved_shorts_filters_channel():
    store, sent = make_store([{"results": [page("p1", "YT-1")], "has_more": False}])
    assert [p.content_id for p in store.approved_shorts()] == ["YT-1"]
    conds = sent[0][2]["filter"]["and"]
    assert {"property": "status", "select": {"equals": "APPROVED"}} in conds
    assert {"property": "채널", "select": {"equals": "YT-쇼핑"}} in conds


def test_page_blocks_paginates():
    store, sent = make_store([
        {"results": [{"type": "heading_2"}], "has_more": True, "next_cursor": "c2"},
        {"results": [{"type": "paragraph"}], "has_more": False},
    ])
    assert [b["type"] for b in store.page_blocks("page-1")] == ["heading_2", "paragraph"]
    assert sent[0][:2] == ("GET", "/v1/blocks/page-1/children")
    assert sent[1][:2] == ("GET", "/v1/blocks/page-1/children")


def test_mark_rendered_sets_status_and_clears_error():
    store, sent = make_store([{}])
    store.mark_rendered(post())
    props = sent[0][2]["properties"]
    assert props["status"] == {"select": {"name": "RENDERED"}}
    assert props["오류"] == {"rich_text": []}
    assert "영상 링크" not in props


def test_lexicon_reads_table_rows_skipping_header():
    def row(a, b):
        return {"type": "table_row", "table_row": {"cells": [[{"plain_text": a}], [{"plain_text": b}]]}}

    store, sent = make_store([
        {"results": [{"type": "paragraph", "id": "b0"},
                     {"type": "table", "id": "t1", "table": {"has_column_header": True}}], "has_more": False},
        {"results": [row("글자", "읽기"), row(" 3M ", "쓰리엠"), row("빈칸", "")], "has_more": False},
    ])
    assert store.lexicon("lex-page") == {"3M": "쓰리엠"}
    assert [s[1] for s in sent] == ["/v1/blocks/lex-page/children", "/v1/blocks/t1/children"]


def test_approved_drama_filters_long_channel():
    store, sent = make_store([{"results": [page("p1", "YT-롱폼-1")], "has_more": False}])
    assert [p.content_id for p in store.approved_drama()] == ["YT-롱폼-1"]
    assert {"property": "채널", "select": {"equals": "YT-롱폼"}} in sent[0][2]["filter"]["and"]


def test_tables_reads_all_rows_with_header_flag():
    def row(*cells):
        return {"type": "table_row", "table_row": {"cells": [[{"plain_text": c}] for c in cells]}}

    store, sent = make_store([
        {"results": [{"type": "table", "id": "t1", "table": {"has_column_header": True}}], "has_more": False},
        {"results": [row("인물", "목소리"), row(" 아들 ", "ko-KR-Neural2-C")], "has_more": False},
    ])
    [t] = store.tables("series-1")
    assert t.id == "t1" and t.header and t.rows == [["인물", "목소리"], ["아들", "ko-KR-Neural2-C"]]


def test_mark_rendered_with_link():
    store, sent = make_store([{}])
    store.mark_rendered(post(), "https://drive/x")
    assert sent[0][2]["properties"]["영상 링크"] == {"url": "https://drive/x"}


def test_missing_media_folders_filter():
    store, sent = make_store([{"results": [page("p1", "YT-1")], "has_more": False}])
    assert [p.content_id for p in store.missing_media_folders()] == ["YT-1"]
    conds = sent[0][2]["filter"]["and"]
    assert {"or": [{"property": "채널", "select": {"equals": "YT-쇼핑"}},
                   {"property": "채널", "select": {"equals": "YT-롱폼"}}]} in conds
    assert {"or": [{"property": "status", "select": {"equals": "DRAFT"}},
                   {"property": "status", "select": {"equals": "APPROVED"}}]} in conds
    assert {"property": "자료 폴더", "url": {"is_empty": True}} in conds


def test_set_media_folder():
    store, sent = make_store([{}])
    store.set_media_folder(post(), "https://drive/f")
    assert sent[0][2]["properties"] == {"자료 폴더": {"url": "https://drive/f"}}


def make_series_store(responses):
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append((req.method, req.url.path, json.loads(req.content or b"{}")))
        return httpx.Response(200, json=responses.pop(0) if responses else {})

    http = httpx.Client(base_url=API, transport=httpx.MockTransport(handler))
    return NotionStore("ntn-token", DbIds("db-c", "db-m", "db-f", series="db-s"), http=http), sent


def test_approved_plans_filter():
    store, sent = make_store([{"results": [page("p1", "YT-롱폼-1")], "has_more": False}])
    assert [p.content_id for p in store.approved_plans()] == ["YT-롱폼-1"]
    conds = sent[0][2]["filter"]["and"]
    assert {"property": "status", "select": {"equals": "기획승인"}} in conds
    assert {"property": "채널", "select": {"equals": "YT-롱폼"}} in conds


def test_find_series_by_title():
    store, sent = make_series_store([{"results": [{"id": "s1"}], "has_more": False}])
    assert store.find_series("시험 시리즈") == "s1"
    assert sent[0][1] == "/v1/databases/db-s/query"
    assert sent[0][2]["filter"] == {"property": "이름", "title": {"equals": "시험 시리즈"}}


def test_series_episodes_by_relation():
    store, sent = make_store([{"results": [page("p1", "YT-롱폼-1")], "has_more": False}])
    assert [p.content_id for p in store.series_episodes("s1")] == ["YT-롱폼-1"]
    assert sent[0][2]["filter"] == {"property": "시리즈", "relation": {"contains": "s1"}}


def test_create_page_and_append_blocks_in_chunks():
    store, sent = make_store([{"id": "new-page"}, {"results": [{"id": "b"}] * 100}, {"results": [{"id": "c"}] * 5}])
    assert store.create_page({"content_id": {"title": []}}, [{"type": "paragraph"}]) == "new-page"
    assert sent[0][1] == "/v1/pages" and sent[0][2]["parent"] == {"database_id": "db-c"}
    assert sent[0][2]["children"] == [{"type": "paragraph"}]
    created = store.append_blocks("blk", [{"type": "paragraph"}] * 105)
    assert len(created) == 105 and [s[0] for s in sent[1:]] == ["PATCH", "PATCH"]
    assert len(sent[1][2]["children"]) == 100 and len(sent[2][2]["children"]) == 5


def test_add_table_rows():
    store, sent = make_store([{}])
    store.add_table_rows("t1", [["며느리", "ko-KR-Neural2-A"]])
    assert sent[0][1] == "/v1/blocks/t1/children"
    row = sent[0][2]["children"][0]
    assert row["type"] == "table_row"
    assert row["table_row"]["cells"][0] == [{"type": "text", "text": {"content": "며느리"}}]


def test_mark_written_sets_draft_and_summary():
    store, sent = make_store([{}])
    store.mark_written(post(), "갈등: …")
    props = sent[0][2]["properties"]
    assert props["status"] == {"select": {"name": "DRAFT"}}
    assert props["회차 요약"] == {"rich_text": [{"text": {"content": "갈등: …"}}]}
