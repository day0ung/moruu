"""Notion 페이지 → Post."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core import schema as S

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Post:
    page_id: str
    content_id: str
    role: str
    text: str
    link: str | None
    disclosure: str
    scheduled_at: datetime | None
    posted_at: datetime | None = None
    media_id: str | None = None
    collected: frozenset[int] = frozenset()
    voice: str = ""
    series: str = ""  # 롱폼: 연결된 시리즈 페이지 ID


def _plain(prop: dict) -> str:
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(i.get("plain_text", "") for i in items)


def _select(prop: dict) -> str:
    s = prop.get("select")
    return s["name"] if s else ""


def _date(prop: dict) -> datetime | None:
    d = prop.get("date")
    if not d:
        return None
    dt = datetime.fromisoformat(d["start"])
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def parse_post(page: dict) -> Post:
    props = page["properties"]

    def get(name: str) -> dict:
        return props.get(name) or {}

    return Post(
        page_id=page["id"],
        content_id=_plain(get(S.TITLE_ID)),
        role=_select(get(S.ROLE)),
        text=_plain(get(S.TEXT)),
        link=get(S.LINK).get("url") or None,
        disclosure=_plain(get(S.DISCLOSURE)),
        scheduled_at=_date(get(S.SCHEDULED)),
        posted_at=_date(get(S.POSTED_AT)),
        media_id=_plain(get(S.MEDIA_ID)) or None,
        collected=frozenset(h for h, name in S.COLLECTED.items() if get(name).get("checkbox")),
        voice=_select(get(S.VOICE)),
        series=next((r["id"] for r in get(S.SERIES).get("relation") or []), ""),
    )
