from dataclasses import replace
from datetime import datetime, timedelta

from core.models import KST, Post
from core.safety import THREADS_MAX_CHARS, blocking_problems, hold_reasons

NOW = datetime(2026, 11, 1, 20, 0, tzinfo=KST)
P = Post("page-1", "TH-1", "정보", "본문", None, "", NOW)


def posted(cid, role, hours_ago):
    return replace(P, content_id=cid, role=role, posted_at=NOW - timedelta(hours=hours_ago), media_id="m")


def test_ok_post_has_no_problems():
    assert blocking_problems(P) == []
    assert hold_reasons(P, [], 3, NOW) == []


def test_empty_or_too_long_text_blocks():
    assert blocking_problems(replace(P, text="  "))
    assert blocking_problems(replace(P, text="가" * (THREADS_MAX_CHARS + 1)))


def test_link_without_disclosure_blocks():
    reasons = blocking_problems(replace(P, link="https://link.coupang.com/a/x", disclosure=""))
    assert any("대가성" in r for r in reasons)


def test_already_posted_blocks():
    assert blocking_problems(replace(P, media_id="m1"))


def test_daily_cap_holds_only_same_kst_day():
    today = [posted(f"T{i}", "정보", i + 1) for i in range(3)]
    assert hold_reasons(P, today, 3, NOW)
    yesterday = [posted(f"T{i}", "정보", 21 + i) for i in range(3)]
    assert hold_reasons(P, yesterday, 3, NOW) == []


def test_revenue_after_revenue_holds():
    rev = replace(P, role="수익", link="https://x", disclosure="문구")
    assert hold_reasons(rev, [posted("T0", "정보", 5), posted("T1", "수익", 2)], 3, NOW)
    assert hold_reasons(rev, [posted("T1", "수익", 5), posted("T2", "정보", 2)], 3, NOW) == []


def test_same_content_id_in_recent_is_held():
    assert blocking_problems(P) == []
    assert hold_reasons(P, [posted("TH-1", "정보", 1)], 3, NOW)
