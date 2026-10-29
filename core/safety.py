"""게시 전 안전 규칙 (PLAN.md §7).
blocking_problems → 사람이 고쳐야 함 (FAILED). hold_reasons → 다음 실행으로 미룸 (APPROVED 유지)."""
from __future__ import annotations

import re
from datetime import datetime

from core import schema as S
from core.models import KST, Post

THREADS_MAX_CHARS = 500
BANNED_WORDS = ("최고", "필수", "무조건", "혁신적")  # CLAUDE.md 절대 규칙


def banned_words(text: str) -> list[str]:
    return [w for w in BANNED_WORDS if w in text]


def blocking_problems(post: Post) -> list[str]:
    problems = []
    if not post.text.strip():
        problems.append("본문 비어 있음")
    if len(post.text) > THREADS_MAX_CHARS:
        problems.append(f"본문 {THREADS_MAX_CHARS}자 초과 ({len(post.text)}자)")
    if post.link and not post.disclosure.strip():
        problems.append("링크가 있는데 대가성문구 없음")
    if re.search(r"https?://|www\.|coupa\.ng|link\.coupang", post.text, re.IGNORECASE):
        problems.append("본문에 링크 있음 — 링크 칸에 넣을 것")
    if post.role == S.ROLE_REVENUE and not post.link:
        problems.append("수익 글인데 링크 없음")
    if post.link and len(f"{post.link}\n\n{post.disclosure}") > THREADS_MAX_CHARS:
        problems.append(f"링크+대가성문구 {THREADS_MAX_CHARS}자 초과")
    if post.media_id:
        problems.append("이미 게시ID 있음")
    return problems


def hold_reasons(post: Post, recent: list[Post], daily_cap: int, now: datetime) -> list[str]:
    reasons = []
    done = [p for p in recent if p.posted_at]
    if any(p.content_id == post.content_id for p in done):
        reasons.append("같은 content_id 최근 게시됨")
    today = now.astimezone(KST).date()
    if sum(p.posted_at.astimezone(KST).date() == today for p in done) >= daily_cap:
        reasons.append(f"하루 상한 {daily_cap}개 도달")
    if post.role == S.ROLE_REVENUE and done:
        last = max(done, key=lambda p: p.posted_at)
        if last.role == S.ROLE_REVENUE:
            reasons.append("수익 글 연속 금지")
    return reasons
