import logging
from datetime import datetime, timedelta

import httpx
import pytest

from channels.threads.client import ThreadsError
from core.models import KST
from fakes import FakeClient, FakeStore, make_post
from pipelines.threads_post.publish import run_publish

NOW = datetime(2026, 11, 1, 8, 5, tzinfo=KST)
LOG = logging.getLogger("moruu")
LINK = dict(role="수익", link="https://link.coupang.com/a/x", disclosure="쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다.")


def run(store, client, **kw):
    return run_publish(store, client, 3, NOW, LOG, sleep=lambda s: None, **kw)


def test_posts_body_then_link_reply():
    store, client = FakeStore(due=[make_post(**LINK)]), FakeClient()
    assert run(store, client) == ["TH-LIVING-20261101-001"]
    assert client.calls[0] == ("좁은 집 수납 팁", None)
    assert client.calls[1] == (LINK["link"] + "\n\n" + LINK["disclosure"], "m1")
    assert store.posted == [("TH-LIVING-20261101-001", "m1", "m2")]


def test_post_without_link_has_no_reply():
    store, client = FakeStore(due=[make_post()]), FakeClient()
    run(store, client)
    assert len(client.calls) == 1
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]


def test_missing_disclosure_fails_without_posting():
    store, client = FakeStore(due=[make_post(link="https://x", disclosure="")]), FakeClient()
    assert run(store, client) == []
    assert client.calls == []
    assert "대가성" in store.failed[0][1]


def test_daily_cap_holds_without_failing():
    recent = [make_post(content_id=f"T{i}", posted_at=NOW - timedelta(minutes=10 + i), media_id="m") for i in range(3)]
    store, client = FakeStore(due=[make_post()], recent=recent), FakeClient()
    assert run(store, client) == []
    assert client.calls == [] and store.failed == []


def test_second_revenue_post_in_same_run_is_held():
    a = make_post(content_id="A", **LINK)
    b = make_post(content_id="B", page_id="page-2", **LINK)
    store, client = FakeStore(due=[a, b]), FakeClient()
    assert run(store, client) == ["A"]


def test_retries_then_succeeds():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=2)
    assert run(store, client) == ["TH-LIVING-20261101-001"]
    assert len(client.calls) == 3


def test_gives_up_after_retries():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=3)
    assert run(store, client) == []
    assert store.failed and store.failures == [("TH-LIVING-20261101-001", "post", "1", "FAILED")]


def test_reply_failure_still_marks_posted_and_logs():
    store, client = FakeStore(due=[make_post(**LINK)]), FakeClient()
    original = client.post_text

    def flaky(text, reply_to=None):
        if reply_to:
            raise ThreadsError("1", "reply boom")
        return original(text, reply_to)

    client.post_text = flaky
    run(store, client)
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]
    assert store.failures[0][1] == "reply"


def test_dry_run_makes_no_calls():
    store, client = FakeStore(due=[make_post()]), FakeClient()
    assert run(store, client, dry_run=True) == []
    assert client.calls == [] and store.posted == []


def test_token_expired_aborts():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=1, error_code="190")
    with pytest.raises(ThreadsError):
        run(store, client)
    assert len(client.calls) == 1


def test_no_quota_stops():
    store, client = FakeStore(due=[make_post()]), FakeClient(quota=0)
    assert run(store, client) == []
    assert client.calls == []


def test_dry_run_blocking_post_is_not_marked_failed():
    store, client = FakeStore(due=[make_post(link="https://x", disclosure="")]), FakeClient()
    assert run(store, client, dry_run=True) == []
    assert store.failed == [] and client.calls == []


def test_marks_posting_before_post():
    store, client = FakeStore(due=[make_post()]), FakeClient()
    assert run(store, client) == ["TH-LIVING-20261101-001"]
    assert store.posting == ["TH-LIVING-20261101-001"]
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]


def test_mark_posted_failure_stops_run():
    store, client = FakeStore(due=[make_post()], fail_mark_posted=True), FakeClient()
    with pytest.raises(RuntimeError):
        run(store, client)
    assert store.posting == ["TH-LIVING-20261101-001"]
    assert len(client.calls) == 1


def test_network_error_fails_without_retry():
    class NetworkDown(FakeClient):
        def post_text(self, text, reply_to=None):
            self.calls.append((text, reply_to))
            raise httpx.ConnectError("boom")

    store, client = FakeStore(due=[make_post()]), NetworkDown()
    assert run(store, client) == []
    assert len(client.calls) == 1
    assert "network" in store.failed[0][1]
    assert store.failures[0][2] == "network"


def test_reply_token_expired_marks_posted_then_raises():
    store, client = FakeStore(due=[make_post(**LINK)]), FakeClient()
    original = client.post_text

    def expired(text, reply_to=None):
        if reply_to:
            raise ThreadsError("190", "expired")
        return original(text, reply_to)

    client.post_text = expired
    with pytest.raises(ThreadsError):
        run(store, client)
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]
