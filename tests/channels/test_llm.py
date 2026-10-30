import json
import logging

import httpx
import pytest

from channels.llm.client import LLM, LLMError, LLMQuotaError, Provider, extract_json

KEY_A, KEY_B = "key-aaaaaaaaaaaa", "key-bbbbbbbbbbbb"


def ok(text, tokens=10):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                     "usage": {"total_tokens": tokens}})


def make(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    providers = [Provider("gemini", "https://g.example/v1beta/openai", KEY_A, {"write": "gm-w", "light": "gm-l"}),
                 Provider("openrouter", "https://o.example/api/v1", KEY_B, {"write": "or-w"})]
    return LLM(providers, http=http, retry_wait=0)


def test_chat_posts_openai_compatible_request():
    sent = []

    def handler(req):
        sent.append((str(req.url), req.headers["Authorization"], json.loads(req.content)))
        return ok("안녕")

    reply = make(handler).chat([{"role": "user", "content": "hi"}], "write")
    assert (reply.text, reply.provider, reply.model, reply.tokens) == ("안녕", "gemini", "gm-w", 10)
    url, auth, body = sent[0]
    assert url == "https://g.example/v1beta/openai/chat/completions" and auth == f"Bearer {KEY_A}"
    assert body["model"] == "gm-w" and body["messages"] == [{"role": "user", "content": "hi"}]


def test_429_falls_back_to_next_provider():
    hosts = []

    def handler(req):
        hosts.append(req.url.host)
        return httpx.Response(429, json={"error": {"message": "quota"}}) if req.url.host == "g.example" else ok("대체")

    assert make(handler).chat([{"role": "user", "content": "x"}], "write").provider == "openrouter"
    assert hosts == ["g.example", "o.example"]


def test_provider_without_role_model_is_skipped_and_all_quota_raises():
    def handler(req):
        return httpx.Response(429, json={"error": {"message": "quota"}})

    llm = make(handler)
    with pytest.raises(LLMQuotaError):
        llm.chat([{"role": "user", "content": "x"}], "light")  # openrouter 는 light 모델 없음 → gemini 만


def test_server_error_retries_once_then_next():
    calls = []

    def handler(req):
        calls.append(req.url.host)
        return httpx.Response(503) if req.url.host == "g.example" else ok("ok")

    assert make(handler).chat([{"role": "user", "content": "x"}], "write").text == "ok"
    assert calls == ["g.example", "g.example", "o.example"]


def test_other_error_raises_without_key(caplog):
    caplog.set_level(logging.INFO)

    def handler(req):
        return httpx.Response(400, json={"error": {"message": "bad model"}})

    with pytest.raises(LLMError) as e:
        make(handler).chat([{"role": "user", "content": "x"}], "write")
    assert "bad model" in str(e.value) and KEY_A not in str(e.value) and KEY_A not in caplog.text


def test_chat_json_retries_once_on_bad_json():
    replies = iter(["설명만 있음", '설명\n```json\n{"a": [1, 2]}\n```'])

    def handler(req):
        return ok(next(replies))

    assert make(handler).chat_json([{"role": "user", "content": "x"}], "write") == {"a": [1, 2]}


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('앞말 {"a": {"b": "}"}} 뒷말') == {"a": {"b": "}"}}
    assert extract_json('```json\n[1, 2]\n```') == [1, 2]
    with pytest.raises(ValueError):
        extract_json("없음")


def test_error_message_from_list_body():
    def handler(req):
        return httpx.Response(403, json=[{"error": {"code": 403, "message": "free tier is not available"}}])

    with pytest.raises(LLMError) as e:
        make(handler).chat([{"role": "user", "content": "x"}], "light")
    assert "free tier is not available" in str(e.value)
