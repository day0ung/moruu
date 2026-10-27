"""Threads 장기 토큰 최초 발급 (get_token.ps1 대체, Windows·Mac 공통).
실행: uv run python -m channels.threads.get_token
threads-auth-page 에서 받은 인증 코드 → 단기 토큰 → 장기 토큰 → .env 저장."""
from __future__ import annotations

import getpass
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from dotenv import dotenv_values

from channels.threads.client import BASE, ThreadsError
from channels.threads.token import update_env_file

REDIRECT_URI = "https://threads-auth.netlify.app/"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Issued:
    token: str
    expires_in: int
    user_id: str
    username: str


def clean_code(code: str) -> str:
    code = code.strip()
    return code[:-2] if code.endswith("#_") else code


def _json(r: httpx.Response) -> dict:
    if r.is_error:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        raise ThreadsError(str(err.get("code", r.status_code)), err.get("message", r.reason_phrase))
    return r.json()


def exchange_code(http: httpx.Client, app_id: str, app_secret: str, code: str) -> Issued:
    short = _json(http.post("/oauth/access_token", data={
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }))["access_token"]
    long = _json(http.get("/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short,
    }))
    me = _json(http.get("/v1.0/me", params={"fields": "id,username", "access_token": long["access_token"]}))
    return Issued(long["access_token"], int(long["expires_in"]), str(me["id"]), me["username"])


def main() -> int:
    cfg = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    app_id = cfg.get("THREADS_APP_ID")
    if not app_id:
        print(f"THREADS_APP_ID 값이 비어 있습니다 ({ENV_PATH} 확인)")
        return 1
    updates: dict[str, str] = {}
    secret = cfg.get("THREADS_APP_SECRET")
    if not secret:
        secret = getpass.getpass("Threads 앱 시크릿 붙여넣기 (화면에 안 보임): ").strip()
        updates["THREADS_APP_SECRET"] = secret
    code = cfg.get("THREADS_AUTH_CODE") or input("인증 코드 붙여넣기: ")
    try:
        with httpx.Client(base_url=BASE, timeout=30) as http:
            issued = exchange_code(http, app_id, secret, clean_code(code))
    except ThreadsError as e:
        print(f"실패: {e}")
        return 1
    updates |= {
        "THREADS_USER_ID": issued.user_id,
        "THREADS_ACCESS_TOKEN": issued.token,
        "THREADS_TOKEN_ISSUED": date.today().isoformat(),
    }
    update_env_file(ENV_PATH, updates, remove=["THREADS_AUTH_CODE"])
    print(f"성공: @{issued.username} / 유효기간 {issued.expires_in // 86400}일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
