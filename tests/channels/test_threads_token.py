from datetime import date

from channels.threads.token import needs_refresh, persist_token, update_env_file


def test_needs_refresh_after_50_days():
    assert not needs_refresh(date(2026, 10, 1), date(2026, 11, 19))
    assert needs_refresh(date(2026, 10, 1), date(2026, 11, 20))


def test_update_env_file_replaces_and_keeps_others(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes("THREADS_APP_ID=1\r\nTHREADS_ACCESS_TOKEN=old\r\n# 메모\r\n".encode("utf-8"))
    update_env_file(env, {"THREADS_ACCESS_TOKEN": "new", "THREADS_TOKEN_ISSUED": "2026-11-20"})
    assert env.read_text(encoding="utf-8").splitlines() == [
        "THREADS_APP_ID=1",
        "THREADS_ACCESS_TOKEN=new",
        "# 메모",
        "THREADS_TOKEN_ISSUED=2026-11-20",
    ]


def test_persist_token_local_writes_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    persist_token("new", date(2026, 11, 20), env_path=env, environ={})
    assert "THREADS_ACCESS_TOKEN=new" in env.read_text(encoding="utf-8")


def test_persist_token_in_actions_uses_gh_secret(tmp_path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw["input"], kw["env"]["GH_TOKEN"]))

    environ = {"GITHUB_ACTIONS": "true", "GH_PAT": "pat", "GITHUB_REPOSITORY": "me/moruu"}
    persist_token("new", date(2026, 11, 20), env_path=tmp_path / ".env", environ=environ, run=fake_run)
    assert calls[0] == (["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", "me/moruu"], "new", "pat")
    assert calls[1][0][3] == "THREADS_TOKEN_ISSUED"
    assert calls[1][1] == "2026-11-20"
    assert not (tmp_path / ".env").exists()
