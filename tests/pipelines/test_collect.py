import logging
from datetime import datetime, timedelta

import httpx

from core.models import KST
from fakes import FakeClient, FakeStore, make_post
from pipelines.threads_post.collect import run_collect

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=KST)
LOG = logging.getLogger("moruu")


def posted(hours_ago, collected=frozenset()):
    return make_post(posted_at=NOW - timedelta(hours=hours_ago), media_id="m1", collected=frozenset(collected))


def test_collects_24h_milestone():
    store, client = FakeStore(recent=[posted(30)]), FakeClient(insights={"views": 120})
    assert run_collect(store, client, NOW, LOG) == 1
    assert store.metrics == [("TH-LIVING-20261101-001", 24, 30.0, {"views": 120})]
    assert store.collected == [("TH-LIVING-20261101-001", [24])]


def test_missed_milestones_record_largest_only():
    store, client = FakeStore(recent=[posted(80)]), FakeClient()
    run_collect(store, client, NOW, LOG)
    assert [m[1] for m in store.metrics] == [72]
    assert store.collected == [("TH-LIVING-20261101-001", [24, 72])]


def test_already_collected_is_skipped():
    store, client = FakeStore(recent=[posted(30, {24})]), FakeClient()
    assert run_collect(store, client, NOW, LOG) == 0
    assert client.calls == []


def test_too_early_is_skipped():
    store, client = FakeStore(recent=[posted(10)]), FakeClient()
    assert run_collect(store, client, NOW, LOG) == 0


def test_insight_error_is_logged_and_continues():
    store = FakeStore(recent=[posted(30), make_post(content_id="B", page_id="p2", posted_at=NOW - timedelta(hours=30), media_id="m2")])
    client = FakeClient(fail_times=1)
    assert run_collect(store, client, NOW, LOG) == 1
    assert store.failures[0][1] == "insight"


def test_network_error_is_logged_and_continues():
    store = FakeStore(recent=[posted(30), make_post(content_id="B", page_id="p2", posted_at=NOW - timedelta(hours=30), media_id="m2")])
    client = FakeClient()
    real_insights = client.insights
    calls = {"n": 0}

    def flaky_insights(media_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return real_insights(media_id)

    client.insights = flaky_insights
    assert run_collect(store, client, NOW, LOG) == 1
    assert store.failures[0][2] == "network"
