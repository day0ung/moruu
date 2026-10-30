"""Google Drive v3 (REST) — 폴더 찾기·만들기, 목록, 받기, 이어 올리기.

refresh token 으로 access token 을 받아 메모리에만 둔다. 오류에는 HTTP 상태와 응답 메시지만 담는다 (토큰·시크릿 없음).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://www.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FOLDER_MIME = "application/vnd.google-apps.folder"
_FIELDS = "nextPageToken,files(id,name,mimeType,size)"


class DriveError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"[{status}] {message}")
        self.status, self.message = status, message


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime: str
    size: int | None  # 폴더는 None


def file_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _error(r: httpx.Response) -> DriveError:
    try:
        err = r.json().get("error")
    except (ValueError, AttributeError):
        err = None
    message = err.get("message") if isinstance(err, dict) else err
    return DriveError(r.status_code, str(message or r.reason_phrase))


def _file(d: dict) -> DriveFile:
    return DriveFile(d["id"], d.get("name", ""), d.get("mimeType", ""), int(d["size"]) if "size" in d else None)


class DriveClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=120)
        self._cred = {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token,
                      "grant_type": "refresh_token"}
        self._token: str | None = None

    def _refresh(self) -> None:
        r = self._http.post(TOKEN_URL, data=self._cred)
        if r.is_error:
            raise _error(r)
        self._token = r.json()["access_token"]

    def _req(self, method: str, url: str, **kw) -> httpx.Response:
        """401 이면 토큰을 한 번 새로 받아 다시 시도. 308(이어 올리기 진행 중)은 정상."""
        for attempt in (0, 1):
            if self._token is None:
                self._refresh()
            headers = {**kw.pop("headers", {}), "Authorization": f"Bearer {self._token}"}
            r = self._http.request(method, url if url.startswith("http") else API + url, headers=headers, **kw)
            if r.status_code == 401 and attempt == 0:
                self._token = None
                kw["headers"] = {k: v for k, v in headers.items() if k != "Authorization"}
                continue
            if r.is_error:
                raise _error(r)
            return r
        raise AssertionError("도달 안 함")

    def _files(self, q: str) -> list[DriveFile]:
        params = {"q": q, "fields": _FIELDS, "pageSize": 1000}
        out: list[DriveFile] = []
        while True:
            data = self._req("GET", "/drive/v3/files", params=params).json()
            out += [_file(f) for f in data.get("files", [])]
            if not data.get("nextPageToken"):
                return out
            params["pageToken"] = data["nextPageToken"]

    def child(self, parent_id: str, name: str) -> DriveFile | None:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        found = self._files(f"'{parent_id}' in parents and name = '{escaped}' and trashed = false")
        return found[0] if found else None

    def ensure_folder(self, parent_id: str, name: str) -> str:
        found = self.child(parent_id, name)
        if found:
            return found.id
        body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        return self._req("POST", "/drive/v3/files", json=body, params={"fields": "id"}).json()["id"]

    def list(self, folder_id: str) -> list[DriveFile]:
        return self._files(f"'{folder_id}' in parents and trashed = false")

    def meta(self, file_id: str) -> DriveFile:
        return _file(self._req("GET", f"/drive/v3/files/{file_id}", params={"fields": "id,name,mimeType,size"}).json())

    def download(self, file_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._req("GET", f"/drive/v3/files/{file_id}", params={"alt": "media"}).content)

    def upload(self, path: Path, folder_id: str, chunk: int = 8 * 1024 * 1024) -> str:
        """이어 올리기. 같은 이름 파일이 있으면 그 파일의 새 버전으로 (링크 유지). 파일 id 를 돌려준다."""
        existing = self.child(folder_id, path.name)
        if existing:
            start = self._req("PATCH", f"/upload/drive/v3/files/{existing.id}",
                              params={"uploadType": "resumable"}, json={})
        else:
            start = self._req("POST", "/upload/drive/v3/files", params={"uploadType": "resumable"},
                              json={"name": path.name, "parents": [folder_id]})
        session = start.headers["Location"]
        total = path.stat().st_size
        with path.open("rb") as f:
            offset = 0
            while True:
                data = f.read(chunk)
                end = offset + len(data) - 1
                r = self._req("PUT", session, content=data,
                              headers={"Content-Range": f"bytes {offset}-{end}/{total}" if data else f"bytes */{total}"})
                if r.status_code in (200, 201):
                    return r.json()["id"]
                offset = end + 1
