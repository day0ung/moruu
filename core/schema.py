"""Notion 속성 이름과 값 빌더. Notion 에서 이름을 바꾸면 여기와 docs/notion-schema.md 를 같이 바꾼다."""
from __future__ import annotations

from datetime import datetime

# 콘텐츠 DB
TITLE_ID = "content_id"
CHANNEL = "채널"
ROLE = "역할"
TEXT = "본문"
LINK = "링크"
DISCLOSURE = "대가성문구"
STATUS = "status"
SCHEDULED = "예약시각"
POSTED_AT = "게시시각"
MEDIA_ID = "게시ID"
REPLY_ID = "댓글ID"
ERROR = "오류"
COLLECTED = {24: "수집_24h", 72: "수집_72h", 168: "수집_7d"}

CH_THREADS = "Threads"
APPROVED = "APPROVED"
POSTING = "POSTING"
POSTED = "POSTED"
FAILED = "FAILED"
ROLE_REVENUE = "수익"

# 성과 DB
M_TITLE = "기록"
M_CONTENT_ID = "content_id"
M_MILESTONE = "경과"
M_ACTUAL_H = "실제경과h"
M_COLLECTED_AT = "수집시각"
MILESTONE_LABEL = {24: "24h", 72: "72h", 168: "7d"}
METRIC_PROPS = {"views": "조회", "likes": "좋아요", "replies": "댓글", "reposts": "리포스트", "quotes": "인용"}

# 실패 로그 DB
F_TITLE = "요약"
F_CONTENT_ID = "content_id"
F_STEP = "step"
F_CODE = "error_code"
F_MESSAGE = "message"
F_RETRY = "retry_count"
F_FINAL = "final_status"
F_TIME = "time"

_MAX = 2000  # Notion rich_text 한 덩어리 최대 길이


def title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:_MAX]}}]}


def rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:_MAX]}}]}


def select(name: str) -> dict:
    return {"select": {"name": name}}


def date(dt: datetime) -> dict:
    return {"date": {"start": dt.isoformat()}}


def number(value: float) -> dict:
    return {"number": value}


def checkbox(value: bool) -> dict:
    return {"checkbox": value}
