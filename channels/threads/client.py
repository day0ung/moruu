"""Threads Graph API v1.0 — 텍스트 게시·답글·한도·인사이트·토큰 갱신."""
from __future__ import annotations

import httpx

BASE = "https://graph.threads.net"
TOKEN_EXPIRED = "190"
METRICS = "views,likes,replies,reposts,quotes"


class ThreadsError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class ThreadsClient:
    def __init__(self, user_id: str, token: str, http: httpx.Client | None = None):
        self._uid = user_id
        self._token = token
        self._http = http or httpx.Client(base_url=BASE, timeout=30)

    def _call(self, method: str, path: str, **params) -> dict:
        r = self._http.request(method, path, params={**params, "access_token": self._token})
        if r.is_error:
            try:
                err = r.json().get("error", {})
            except ValueError:
                err = {}
            raise ThreadsError(str(err.get("code", r.status_code)), err.get("message", r.reason_phrase))
        return r.json()

    def post_text(self, text: str, reply_to: str | None = None) -> str:
        params = {"media_type": "TEXT", "text": text}
        if reply_to:
            params["reply_to_id"] = reply_to
        creation_id = self._call("POST", f"/v1.0/{self._uid}/threads", **params)["id"]
        return self._call("POST", f"/v1.0/{self._uid}/threads_publish", creation_id=creation_id)["id"]

    def quota_left(self) -> int:
        data = self._call("GET", f"/v1.0/{self._uid}/threads_publishing_limit", fields="quota_usage,config")
        d = data["data"][0]
        return d["config"]["quota_total"] - d["quota_usage"]

    def insights(self, media_id: str) -> dict[str, int]:
        data = self._call("GET", f"/v1.0/{media_id}/insights", metric=METRICS)
        out = {}
        for m in data["data"]:
            out[m["name"]] = m["values"][0]["value"] if "values" in m else m["total_value"]["value"]
        return out

    def refresh_token(self) -> tuple[str, int]:
        data = self._call("GET", "/refresh_access_token", grant_type="th_refresh_token")
        return data["access_token"], int(data["expires_in"])
