import httpx
import pytest

from channels.threads.client import BASE, ThreadsError
from channels.threads.get_token import REDIRECT_URI, clean_code, exchange_code


def test_clean_code_strips_suffix_and_spaces():
    assert clean_code(" AQBx123#_ \n") == "AQBx123"
    assert clean_code("AQBx123") == "AQBx123"


def make_http(handler):
    return httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))


def test_exchange_code_runs_three_steps():
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path == "/oauth/access_token":
            return httpx.Response(200, json={"access_token": "SHORT", "user_id": 1})
        if req.url.path == "/access_token":
            return httpx.Response(200, json={"access_token": "LONG", "expires_in": 5183944})
        return httpx.Response(200, json={"id": "999", "username": "moruu_home"})

    issued = exchange_code(make_http(handler), "app1", "sec1", "CODE")
    assert issued.token == "LONG"
    assert issued.expires_in == 5183944
    assert (issued.user_id, issued.username) == ("999", "moruu_home")

    form = dict(httpx.QueryParams(seen[0].content.decode()))
    assert seen[0].method == "POST"
    assert form == {
        "client_id": "app1",
        "client_secret": "sec1",
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": "CODE",
    }
    assert seen[1].url.params["grant_type"] == "th_exchange_token"
    assert seen[1].url.params["access_token"] == "SHORT"
    assert seen[2].url.path == "/v1.0/me"
    assert seen[2].url.params["access_token"] == "LONG"


def test_exchange_code_error_has_no_secret():
    def handler(req):
        return httpx.Response(400, json={"error": {"code": 100, "message": "Invalid code"}})

    with pytest.raises(ThreadsError) as e:
        exchange_code(make_http(handler), "app1", "sec1", "CODE")
    assert e.value.code == "100"
    assert "sec1" not in str(e.value)


def _write_env(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_main_success_saves_token_and_hides_secrets(tmp_path, monkeypatch, capsys):
    from channels.threads import get_token

    env = _write_env(tmp_path / ".env", "THREADS_APP_ID=app1\nTHREADS_APP_SECRET=sec1\nTHREADS_AUTH_CODE=CODE#_\n")
    monkeypatch.setattr(get_token, "ENV_PATH", env)
    seen = {}

    def fake_exchange(http, app_id, app_secret, code):
        seen["code"] = code
        return get_token.Issued("LONG", 5184000, "999", "moruu_home")

    monkeypatch.setattr(get_token, "exchange_code", fake_exchange)

    assert get_token.main() == 0
    assert seen["code"] == "CODE"
    text = env.read_text(encoding="utf-8")
    assert "THREADS_ACCESS_TOKEN=LONG" in text
    assert "THREADS_USER_ID=999" in text
    assert "THREADS_AUTH_CODE" not in text
    out = capsys.readouterr().out
    assert "@moruu_home" in out
    assert "LONG" not in out
    assert "sec1" not in out


def test_main_network_failure_keeps_prompted_secret(tmp_path, monkeypatch, capsys):
    from channels.threads import get_token

    env = _write_env(tmp_path / ".env", "THREADS_APP_ID=app1\nTHREADS_AUTH_CODE=CODE\n")
    monkeypatch.setattr(get_token, "ENV_PATH", env)
    monkeypatch.setattr(get_token.getpass, "getpass", lambda prompt="": "sec1")

    def fake_exchange(http, app_id, app_secret, code):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(get_token, "exchange_code", fake_exchange)

    assert get_token.main() == 1
    out = capsys.readouterr().out
    assert "실패" in out
    assert "sec1" not in out
    assert "THREADS_APP_SECRET=sec1" in env.read_text(encoding="utf-8")
