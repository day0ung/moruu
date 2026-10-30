"""Google Drive refresh token 발급 — 브라우저 로그인 → .env 의 GDRIVE_REFRESH_TOKEN.
실행: uv run python -m channels.gdrive.get_token [--check]
필요: .env 의 GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET (데스크톱 앱 OAuth 클라이언트). 절차: docs/TODO-manual.md 6-4."""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import secrets
import sys
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import dotenv_values

from channels.gdrive.client import TOKEN_URL, DriveClient, DriveError
from channels.threads.token import update_env_file

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "https://www.googleapis.com/auth/drive"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def auth_url(client_id: str, redirect: str, challenge: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def exchange(http: httpx.Client, client_id: str, secret: str, code: str, redirect: str, verifier: str) -> str:
    r = http.post(TOKEN_URL, data={"client_id": client_id, "client_secret": secret, "code": code,
                                   "grant_type": "authorization_code", "redirect_uri": redirect,
                                   "code_verifier": verifier})
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.is_error or "refresh_token" not in data:
        raise DriveError(r.status_code, str(data.get("error") or "refresh_token 없음"))
    return data["refresh_token"]


def _receive_code(client_id: str, challenge: str) -> tuple[dict[str, str], str]:
    """127.0.0.1 임시 서버로 브라우저 리디렉션을 받는다 → (쿼리, redirect)."""
    box: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            box.update({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("완료 — 이 창을 닫고 터미널을 보세요.".encode())

        def log_message(self, *args):  # 요청 주소(code 포함)를 찍지 않는다
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}/"
    print("브라우저에서 Google 로그인 → 허용 ('확인되지 않은 앱' 이면 고급 → 이동)")
    webbrowser.open(auth_url(client_id, redirect, challenge))
    while "code" not in box and "error" not in box:
        server.handle_request()
    server.server_close()
    return box, redirect


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gdrive.get_token")
    ap.add_argument("--check", action="store_true", help="저장된 토큰으로 moruu 폴더 접근 확인")
    args = ap.parse_args(argv)
    cfg = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    cid, secret = cfg.get("GDRIVE_CLIENT_ID"), cfg.get("GDRIVE_CLIENT_SECRET")
    if not cid or not secret:
        print("GDRIVE_CLIENT_ID / GDRIVE_CLIENT_SECRET 값이 비어 있습니다 (.env 확인)")
        return 1
    try:
        if args.check:
            if not cfg.get("GDRIVE_REFRESH_TOKEN") or not cfg.get("GDRIVE_ROOT_ID"):
                print("GDRIVE_REFRESH_TOKEN / GDRIVE_ROOT_ID 값이 비어 있습니다")
                return 1
            root = DriveClient(cid, secret, cfg["GDRIVE_REFRESH_TOKEN"]).meta(cfg["GDRIVE_ROOT_ID"])
            print(f"ok: {root.name} 폴더 접근됨")
            return 0
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        box, redirect = _receive_code(cid, challenge)
        if "error" in box:
            print(f"실패: {box['error']}")
            return 1
        with httpx.Client(timeout=30) as http:
            token = exchange(http, cid, secret, box["code"], redirect, verifier)
    except DriveError as e:
        print(f"실패: {e}")
        return 1
    except httpx.HTTPError as e:
        print(f"실패: 네트워크 오류 ({type(e).__name__})")
        return 1
    update_env_file(ENV_PATH, {"GDRIVE_REFRESH_TOKEN": token})
    print("저장됨: GDRIVE_REFRESH_TOKEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
