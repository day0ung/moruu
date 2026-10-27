from datetime import datetime, timedelta

import pytest

import pipelines.threads_post.__main__ as cli
from channels.threads.client import ThreadsError
from core.config import REQUIRED
from core.models import KST

OLD_TOKEN = "OLD-TOKEN"


def test_dry_run_without_config_exits_1_and_never_calls_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)  # 실제 .env 로드 방지
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)

    assert cli.main(["--dry-run"]) == 1
    assert "환경변수 없음" in capsys.readouterr().err


@pytest.fixture
def env(tmp_path, monkeypatch):
    """더미 설정 + 갱신 필요(60일 전 발급) + 실제 I/O 를 가짜로 교체."""
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    issued = (datetime.now(KST).date() - timedelta(days=60)).isoformat()
    values = {
        "THREADS_USER_ID": "uid",
        "THREADS_ACCESS_TOKEN": OLD_TOKEN,
        "THREADS_TOKEN_ISSUED": issued,
        "NOTION_TOKEN": "notion-dummy",
        "NOTION_DB_CONTENT": "db-content",
        "NOTION_DB_METRICS": "db-metrics",
        "NOTION_DB_FAILURES": "db-failures",
    }
    for k, v in values.items():
        monkeypatch.setenv(k, v)

    state = {"refresh": None, "persist": None, "published_with": None}

    class FakeClient:
        def __init__(self, user_id, token, http=None):
            self.token = token

        def refresh_token(self):
            if isinstance(state["refresh"], Exception):
                raise state["refresh"]
            return state["refresh"]

    def fake_publish(store, client, cap, now, log, *, dry_run):
        state["published_with"] = client.token

    def fake_persist(token, issued, *, env_path, environ, **kw):
        if isinstance(state["persist"], Exception):
            raise state["persist"]

    monkeypatch.setattr(cli, "ThreadsClient", FakeClient)
    monkeypatch.setattr(cli, "NotionStore", lambda *a, **k: object())
    monkeypatch.setattr(cli, "run_publish", fake_publish)
    monkeypatch.setattr(cli, "run_collect", lambda *a, **k: 0)
    monkeypatch.setattr(cli, "persist_token", fake_persist)
    return state


def test_refresh_token_expired_returns_2(env):
    env["refresh"] = ThreadsError("190", "expired")

    assert cli.main([]) == 2
    assert env["published_with"] is None  # run_publish 호출 안 됨


def test_persist_failure_continues_and_returns_3(env):
    env["refresh"] = ("NEW", 5184000)
    env["persist"] = RuntimeError("disk full")

    assert cli.main([]) == 3
    assert env["published_with"] == "NEW"  # 게시는 새 토큰으로 계속


def test_refresh_other_error_keeps_old_token(env):
    env["refresh"] = ThreadsError("1", "x")

    assert cli.main([]) == 0
    assert env["published_with"] == OLD_TOKEN
