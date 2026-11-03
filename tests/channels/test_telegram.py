import json
import logging

import httpx

from channels.telegram.client import Telegram

TOKEN = "123456:SECRET-BOT-TOKEN"


def make(handler):
    http = httpx.Client(base_url="https://api.telegram.org", transport=httpx.MockTransport(handler))
    return Telegram(TOKEN, "42", http=http)


def test_send_posts_message():
    sent = []

    def handler(req):
        sent.append((req.url.path, json.loads(req.content)))
        return httpx.Response(200, json={"ok": True})

    assert make(handler).send("가") is True
    assert sent == [(f"/bot{TOKEN}/sendMessage", {"chat_id": "42", "text": "가", "disable_web_page_preview": True})]


def test_send_failure_returns_false_without_token(caplog):
    caplog.set_level(logging.WARNING)
    tg = make(lambda req: httpx.Response(400, json={"ok": False, "description": "chat not found"}))
    assert tg.send("가") is False
    assert "chat not found" in caplog.text and TOKEN not in caplog.text


def test_send_connect_error_returns_false_without_token(caplog):
    caplog.set_level(logging.WARNING)

    def handler(req):
        raise httpx.ConnectError(f"cannot reach {req.url}")

    assert make(handler).send("가") is False
    assert "ConnectError" in caplog.text and TOKEN not in caplog.text


def test_latest_chat_id():
    updates = {"ok": True, "result": [{"message": {"chat": {"id": 1}}}, {"message": {"chat": {"id": 2}}}]}
    assert make(lambda req: httpx.Response(200, json=updates)).latest_chat_id() == "2"
    assert make(lambda req: httpx.Response(200, json={"ok": True, "result": []})).latest_chat_id() is None


def test_send_video_uploads_file(tmp_path):
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"VIDEO")
    seen = []

    def handler(req):
        seen.append((req.url.path, req.headers["content-type"], req.content))
        return httpx.Response(200, json={"ok": True})

    assert make(handler).send_video(mp4, "✅ 완료") is True
    path, ctype, body = seen[0]
    assert path == f"/bot{TOKEN}/sendVideo" and ctype.startswith("multipart/form-data")
    assert b"VIDEO" in body and "✅ 완료".encode() in body and b'name="chat_id"' in body


def test_send_video_too_big_skips_request(tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.WARNING)
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"12345")
    monkeypatch.setattr("channels.telegram.client.VIDEO_MAX_BYTES", 4)
    called = []
    assert make(lambda req: called.append(req) or httpx.Response(200, json={"ok": True})).send_video(mp4, "가") is False
    assert called == [] and "50MB" in caplog.text


def test_send_video_failure_returns_false_without_token(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"V")
    tg = make(lambda req: httpx.Response(400, json={"ok": False, "description": "bad"}))
    assert tg.send_video(mp4, "가") is False
    assert TOKEN not in caplog.text
