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
