"""APPROVED + 예약시각 지난 Threads 글 게시 → 첫 댓글에 링크+대가성 문구."""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta

from channels.threads.client import TOKEN_EXPIRED, ThreadsError
from core.models import Post
from core.safety import blocking_problems, hold_reasons

MAX_RETRY = 2
RETRY_WAIT_SEC = 5


def reply_text(post: Post) -> str:
    return f"{post.link}\n\n{post.disclosure}"


def _with_retry(fn, sleep):
    for attempt in range(MAX_RETRY + 1):
        try:
            return fn()
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED or attempt == MAX_RETRY:
                raise
            sleep(RETRY_WAIT_SEC)


def run_publish(store, client, daily_cap: int, now: datetime, log: logging.Logger, *,
                dry_run: bool = False, sleep=time.sleep) -> list[str]:
    due = store.approved_threads_due(now)
    if not due:
        log.info("게시할 APPROVED 글 없음")
        return []
    recent = store.posted_threads_since(now - timedelta(days=1))
    quota = client.quota_left()
    done: list[str] = []

    for post in due:
        cid = post.content_id
        problems = blocking_problems(post)
        if problems:
            log.warning("%s 게시 불가: %s", cid, ", ".join(problems))
            store.mark_failed(post, ", ".join(problems))
            continue
        reasons = hold_reasons(post, recent, daily_cap, now)
        if reasons:
            log.info("%s 다음 실행으로 보류: %s", cid, ", ".join(reasons))
            continue
        if quota <= 0:
            log.warning("Threads 게시 한도 소진 — 이번 실행 중단")
            break
        if dry_run:
            log.info("[dry-run] 게시 예정: %s", cid)
            continue

        try:
            media_id = _with_retry(lambda: client.post_text(post.text), sleep)
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                raise
            log.error("%s 게시 실패: %s", cid, e)
            store.mark_failed(post, f"post: {e}")
            store.log_failure(cid, "post", e.code, e.message, MAX_RETRY, "FAILED", now)
            continue

        reply_id = None
        if post.link:
            try:
                reply_id = _with_retry(lambda: client.post_text(reply_text(post), reply_to=media_id), sleep)
            except ThreadsError as e:
                if e.code == TOKEN_EXPIRED:
                    store.mark_posted(post, media_id, None, now)
                    raise
                log.error("%s 링크 댓글 실패 (본문은 게시됨): %s", cid, e)
                store.log_failure(cid, "reply", e.code, e.message, MAX_RETRY, "POSTED_NO_REPLY", now)

        store.mark_posted(post, media_id, reply_id, now)
        recent.append(replace(post, posted_at=now, media_id=media_id))
        quota -= 1
        done.append(cid)
        log.info("%s 게시 완료", cid)
    return done
