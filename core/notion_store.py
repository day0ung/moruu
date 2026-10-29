"""Notion API 저장소 — 무인 실행(Actions)용. 대화형 작업은 Notion MCP 로 한다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from core import schema as S
from core.models import Post, parse_post

API = "https://api.notion.com"
NOTION_VERSION = "2022-06-28"


@dataclass(frozen=True)
class DbIds:
    content: str
    metrics: str
    failures: str


class NotionStore:
    def __init__(self, token: str, dbs: DbIds, http: httpx.Client | None = None):
        self._dbs = dbs
        self._http = http or httpx.Client(base_url=API, timeout=30)
        self._headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}

    def _req(self, method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        r = self._http.request(method, path, json=body, params=params, headers=self._headers)
        r.raise_for_status()
        return r.json()

    def _query(self, db_id: str, filter_: dict, sorts: list[dict]) -> list[dict]:
        body = {"filter": filter_, "sorts": sorts, "page_size": 100}
        pages: list[dict] = []
        while True:
            data = self._req("POST", f"/v1/databases/{db_id}/query", body)
            pages += data["results"]
            if not data.get("has_more"):
                return pages
            body["start_cursor"] = data["next_cursor"]

    def _threads(self, status: str, date_prop: str, op: str, when: datetime) -> list[Post]:
        filter_ = {"and": [
            {"property": S.STATUS, "select": {"equals": status}},
            {"property": S.CHANNEL, "select": {"equals": S.CH_THREADS}},
            {"property": date_prop, "date": {op: when.isoformat()}},
        ]}
        pages = self._query(self._dbs.content, filter_, [{"property": date_prop, "direction": "ascending"}])
        return [parse_post(p) for p in pages]

    def approved_threads_due(self, now: datetime) -> list[Post]:
        return self._threads(S.APPROVED, S.SCHEDULED, "on_or_before", now)

    def posted_threads_since(self, since: datetime) -> list[Post]:
        return self._threads(S.POSTED, S.POSTED_AT, "on_or_after", since)

    def approved_shorts(self) -> list[Post]:
        filter_ = {"and": [
            {"property": S.STATUS, "select": {"equals": S.APPROVED}},
            {"property": S.CHANNEL, "select": {"equals": S.CH_YT_SHOP}},
        ]}
        pages = self._query(self._dbs.content, filter_, [{"timestamp": "created_time", "direction": "ascending"}])
        return [parse_post(p) for p in pages]

    def page_blocks(self, page_id: str) -> list[dict]:
        """페이지 본문 최상위 블록 (하위 블록은 읽지 않음)."""
        params = {"page_size": 100}
        blocks: list[dict] = []
        while True:
            data = self._req("GET", f"/v1/blocks/{page_id}/children", params=params)
            blocks += data["results"]
            if not data.get("has_more"):
                return blocks
            params["start_cursor"] = data["next_cursor"]

    def _update(self, page_id: str, props: dict) -> None:
        self._req("PATCH", f"/v1/pages/{page_id}", {"properties": props})

    def _create(self, db_id: str, props: dict) -> None:
        self._req("POST", "/v1/pages", {"parent": {"database_id": db_id}, "properties": props})

    def mark_posting(self, post: Post) -> None:
        self._update(post.page_id, {S.STATUS: S.select(S.POSTING)})

    def mark_approved(self, post: Post) -> None:
        self._update(post.page_id, {S.STATUS: S.select(S.APPROVED)})

    def mark_posted(self, post: Post, media_id: str, reply_id: str | None, at: datetime) -> None:
        props = {S.STATUS: S.select(S.POSTED), S.MEDIA_ID: S.rich(media_id), S.POSTED_AT: S.date(at)}
        if reply_id:
            props[S.REPLY_ID] = S.rich(reply_id)
        self._update(post.page_id, props)

    def mark_failed(self, post: Post, error: str) -> None:
        self._update(post.page_id, {S.STATUS: S.select(S.FAILED), S.ERROR: S.rich(error)})

    def mark_rendered(self, post: Post) -> None:
        self._update(post.page_id, {S.STATUS: S.select(S.RENDERED), S.ERROR: {"rich_text": []}})

    def mark_collected(self, post: Post, hours: list[int]) -> None:
        self._update(post.page_id, {S.COLLECTED[h]: S.checkbox(True) for h in hours})

    def add_metrics(self, post: Post, hours: int, actual_hours: float, metrics: dict[str, int], at: datetime) -> None:
        label = S.MILESTONE_LABEL[hours]
        props = {
            S.M_TITLE: S.title(f"{post.content_id} {label}"),
            S.M_CONTENT_ID: S.rich(post.content_id),
            S.M_MILESTONE: S.select(label),
            S.M_ACTUAL_H: S.number(actual_hours),
            S.M_COLLECTED_AT: S.date(at),
        }
        for key, value in metrics.items():
            if key in S.METRIC_PROPS:
                props[S.METRIC_PROPS[key]] = S.number(value)
        self._create(self._dbs.metrics, props)

    def log_failure(self, content_id: str, step: str, code: str, message: str,
                    retries: int, final: str, at: datetime) -> None:
        self._create(self._dbs.failures, {
            S.F_TITLE: S.title(f"{content_id} {step} {code}"),
            S.F_CONTENT_ID: S.rich(content_id),
            S.F_STEP: S.select(step),
            S.F_CODE: S.rich(code),
            S.F_MESSAGE: S.rich(message),
            S.F_RETRY: S.number(retries),
            S.F_FINAL: S.select(final),
            S.F_TIME: S.date(at),
        })
