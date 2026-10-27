"""APPROVED + 예약시각 지난 Threads 글 게시 → 첫 댓글에 링크+대가성 문구."""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta

import httpx

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


def _record_posted(store, post: Post, media_id: str, reply_id: str | None, now: datetime,
                   log: logging.Logger) -> None:
    try:
        store.mark_posted(post, media_id, reply_id, now)
    except Exception:
        log.error("%s 게시는 됐지만 Notion 기록 실패 (media_id=%s) — Notion 에서 직접 POSTED 처리 필요",
                  post.content_id, media_id)
        raise


RECENT_DAYS = 30  # 중복 content_id 검사 범위


def run_publish(store, client, daily_cap: int, now: datetime, log: logging.Logger, *,
                dry_run: bool = False, sleep=time.sleep) -> list[str]:
    due = store.approved_threads_due(now)
    if not due:
        log.info("게시할 APPROVED 글 없음")
        return []
    recent = store.posted_threads_since(now - timedelta(days=RECENT_DAYS))
    quota = client.quota_left()
    done: list[str] = []

    for post in due:
        cid = post.content_id
        problems = blocking_problems(post)
        if problems:
            if dry_run:
                log.warning("[dry-run] %s 게시 불가: %s", cid, ", ".join(problems))
                continue
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

        store.mark_posting(post)
        try:
            media_id = _with_retry(lambda: client.post_text(post.text), sleep)
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                # 190 이면 게시되지 않았으므로 APPROVED 로 되돌려 다음 실행에서 다시 시도할 수 있게 한다.
                store.mark_approved(post)
                raise
            log.error("%s 게시 실패: %s", cid, e)
            store.mark_failed(post, f"post: {e}")
            store.log_failure(cid, "post", e.code, e.message, MAX_RETRY, "FAILED", now)
            continue
        except httpx.HTTPError as e:
            # 타임아웃이면 실제로 게시됐을 수 있으므로 재시도하지 않는다.
            log.error("%s 게시 네트워크 오류 (Threads 에서 게시 여부 확인 필요): %s", cid, type(e).__name__)
            store.mark_failed(post, "network: 게시 여부를 Threads 에서 확인 필요")
            store.log_failure(cid, "post", "network", type(e).__name__, 0, "FAILED", now)
            continue

        reply_id = None
        if post.link:
            try:
                reply_id = _with_retry(lambda: client.post_text(reply_text(post), reply_to=media_id), sleep)
            except ThreadsError as e:
                if e.code == TOKEN_EXPIRED:
                    _record_posted(store, post, media_id, None, now, log)
                    raise
                log.error("%s 링크 댓글 실패 (본문은 게시됨): %s", cid, e)
                store.log_failure(cid, "reply", e.code, e.message, MAX_RETRY, "POSTED_NO_REPLY", now)
            except httpx.HTTPError as e:
                log.error("%s 링크 댓글 네트워크 오류 (본문은 게시됨): %s", cid, type(e).__name__)
                store.log_failure(cid, "reply", "network", type(e).__name__, 0, "POSTED_NO_REPLY", now)

        _record_posted(store, post, media_id, reply_id, now, log)
        recent.append(replace(post, posted_at=now, media_id=media_id))
        quota -= 1
        done.append(cid)
        log.info("%s 게시 완료", cid)
    return done
