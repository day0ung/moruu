"""게시 후 24h / 72h / 7d 인사이트 → Notion 성과 DB."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from channels.threads.client import TOKEN_EXPIRED, ThreadsError

MILESTONES = (24, 72, 168)


def run_collect(store, client, now: datetime, log: logging.Logger) -> int:
    posts = store.posted_threads_since(now - timedelta(hours=MILESTONES[-1] + 48))
    written = 0
    for post in posts:
        if not post.media_id or not post.posted_at:
            continue
        elapsed = (now - post.posted_at).total_seconds() / 3600
        due = [h for h in MILESTONES if h not in post.collected and elapsed >= h]
        if not due:
            continue
        hours = max(due)
        try:
            metrics = client.insights(post.media_id)
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                raise
            log.error("%s 인사이트 실패: %s", post.content_id, e)
            store.log_failure(post.content_id, "insight", e.code, e.message, 0, "SKIPPED", now)
            continue
        except httpx.HTTPError as e:
            log.error("%s 인사이트 네트워크 오류: %s", post.content_id, type(e).__name__)
            store.log_failure(post.content_id, "insight", "network", type(e).__name__, 0, "SKIPPED", now)
            continue
        store.add_metrics(post, hours, round(elapsed, 1), metrics, now)
        store.mark_collected(post, due)
        written += 1
        log.info("%s %dh 인사이트 기록 (실제 %.1fh)", post.content_id, hours, elapsed)
    return written
