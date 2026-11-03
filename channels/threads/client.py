"""Threads Graph API v1.0 — 텍스트·이미지(캐러셀) 게시·답글·한도·인사이트·토큰 갱신.
이미지는 공개 URL 로 넘긴다 (Threads 서버가 직접 받아 감). JPEG·PNG, 장당 8MB, 캐러셀 2~20장."""
from __future__ import annotations

import time

import httpx

BASE = "https://graph.threads.net"
TOKEN_EXPIRED = "190"
METRICS = "views,likes,replies,reposts,quotes"
MAX_IMAGES = 20
READY_TRIES = 10  # 이미지 처리 대기: 3초 × 10번
READY_WAIT_SEC = 3


class ThreadsError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def raise_for_error(r: httpx.Response) -> None:
    if not r.is_error:
        return
    try:
        body = r.json()
    except ValueError:
        body = {}
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        err = {}
    raise ThreadsError(str(err.get("code", r.status_code)), str(err.get("message") or r.reason_phrase))


class ThreadsClient:
    def __init__(self, user_id: str, token: str, http: httpx.Client | None = None, sleep=time.sleep):
        self._sleep = sleep
        self._uid = user_id
        self._token = token
        self._http = http or httpx.Client(base_url=BASE, timeout=30)

    def _call(self, method: str, path: str, **params) -> dict:
        r = self._http.request(method, path, params={**params, "access_token": self._token})
        raise_for_error(r)
        return r.json()

    def post_text(self, text: str, reply_to: str | None = None) -> str:
        params = {"media_type": "TEXT", "text": text}
        if reply_to:
            params["reply_to_id"] = reply_to
        creation_id = self._call("POST", f"/v1.0/{self._uid}/threads", **params)["id"]
        return self._call("POST", f"/v1.0/{self._uid}/threads_publish", creation_id=creation_id)["id"]

    def post_images(self, text: str, urls: list[str]) -> str:
        """이미지 1장 = IMAGE 글, 2장 이상 = 캐러셀. 처리 끝날 때까지 기다렸다가 게시."""
        if not urls or len(urls) > MAX_IMAGES:
            raise ValueError(f"이미지는 1~{MAX_IMAGES}장")
        path = f"/v1.0/{self._uid}/threads"
        if len(urls) == 1:
            creation_id = self._call("POST", path, media_type="IMAGE", image_url=urls[0], text=text)["id"]
        else:
            children = [self._call("POST", path, media_type="IMAGE", image_url=u, is_carousel_item="true")["id"]
                        for u in urls]
            for c in children:
                self._wait_ready(c)
            creation_id = self._call("POST", path, media_type="CAROUSEL", children=",".join(children), text=text)["id"]
        self._wait_ready(creation_id)
        return self._call("POST", f"/v1.0/{self._uid}/threads_publish", creation_id=creation_id)["id"]

    def _wait_ready(self, container_id: str) -> None:
        for _ in range(READY_TRIES):
            status = self._call("GET", f"/v1.0/{container_id}", fields="status,error_message").get("status")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise ThreadsError("media", f"이미지 처리 실패 ({status})")
            self._sleep(READY_WAIT_SEC)
        raise ThreadsError("media", "이미지 처리 대기 시간 초과")

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
