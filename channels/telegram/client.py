"""텔레그램 봇 알림 — 보내기만 한다. 토큰이 URL 경로에 들어가므로 오류 로그에 URL·예외 문자열을 넣지 않는다."""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

BASE = "https://api.telegram.org"
VIDEO_MAX_BYTES = 50 * 1024 * 1024  # 봇 API 파일 올리기 한도
log = logging.getLogger("moruu")


class Telegram:
    def __init__(self, token: str, chat_id: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=BASE, timeout=20)
        self._token, self.chat_id = token, chat_id

    def _call(self, method: str, body: dict | None = None, files: dict | None = None,
              timeout: float | None = None) -> dict | None:
        kw = {"data": body, "files": files} if files else {"json": body or {}}
        if timeout:
            kw["timeout"] = timeout
        try:
            r = self._http.post(f"/bot{self._token}/{method}", **kw)
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

    def send_video(self, path: Path, caption: str) -> bool:
        """mp4 를 대화방에 올린다. 50MB 넘거나 실패하면 False (예외 없음)."""
        if path.stat().st_size > VIDEO_MAX_BYTES:
            log.warning("텔레그램 영상 생략: %s 가 50MB 를 넘음", path.name)
            return False
        body = {"chat_id": self.chat_id, "caption": caption[:1024], "supports_streaming": "true"}
        with path.open("rb") as f:
            return self._call("sendVideo", body, files={"video": (path.name, f, "video/mp4")}, timeout=300) is not None

    def latest_chat_id(self) -> str | None:
        data = self._call("getUpdates")
        chats = [u["message"]["chat"]["id"] for u in (data or {}).get("result", []) if "message" in u]
        return str(chats[-1]) if chats else None
