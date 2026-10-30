"""텔레그램 봇 알림 — 보내기만 한다. 토큰이 URL 경로에 들어가므로 오류 로그에 URL·예외 문자열을 넣지 않는다."""
from __future__ import annotations

import logging

import httpx

BASE = "https://api.telegram.org"
log = logging.getLogger("moruu")


class Telegram:
    def __init__(self, token: str, chat_id: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=BASE, timeout=20)
        self._token, self.chat_id = token, chat_id

    def _call(self, method: str, body: dict | None = None) -> dict | None:
        try:
            r = self._http.post(f"/bot{self._token}/{method}", json=body or {})
        except httpx.HTTPError as e:
            log.warning("텔레그램 %s 실패: %s", method, type(e).__name__)
            return None
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.is_error or not data.get("ok"):
            log.warning("텔레그램 %s 실패: %s %s", method, r.status_code, data.get("description", ""))
            return None
        return data

    def send(self, text: str) -> bool:
        """실패해도 예외를 내지 않는다 — 알림 때문에 렌더 결과가 바뀌면 안 됨."""
        body = {"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True}
        return self._call("sendMessage", body) is not None

    def latest_chat_id(self) -> str | None:
        data = self._call("getUpdates")
        chats = [u["message"]["chat"]["id"] for u in (data or {}).get("result", []) if "message" in u]
        return str(chats[-1]) if chats else None
