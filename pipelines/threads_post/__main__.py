"""python -m pipelines.threads_post [--dry-run] [--only publish|collect|all]"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from channels.threads.client import TOKEN_EXPIRED, ThreadsClient, ThreadsError
from channels.threads.token import needs_refresh, persist_token
from core.config import ConfigError, Settings
from core.log import setup_logging
from core.models import KST
from core.notion_store import DbIds, NotionStore
from pipelines.threads_post.collect import run_collect
from pipelines.threads_post.publish import run_publish

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="threads_post")
    ap.add_argument("--dry-run", action="store_true", help="게시하지 않고 대상만 출력")
    ap.add_argument("--only", choices=["publish", "collect", "all"], default="all")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = Settings.from_env(os.environ)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    log = setup_logging([s.threads_token, s.notion_token])
    now = datetime.now(KST)

    token = s.threads_token
    exit_code = 0
    if not args.dry_run and needs_refresh(s.threads_token_issued, now.date()):
        try:
            new_token, _ = ThreadsClient(s.threads_user_id, token).refresh_token()
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                log.error("Threads 토큰 만료 — uv run python -m channels.threads.get_token 으로 재발급 필요")
                return 2
            log.warning("Threads 토큰 갱신 실패 — 기존 토큰으로 계속")
            exit_code = 3
        except httpx.HTTPError:
            log.warning("Threads 토큰 갱신 실패 — 기존 토큰으로 계속")
            exit_code = 3
        else:
            token = new_token
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::add-mask::{new_token}")
            log = setup_logging([token, s.threads_token, s.notion_token])
            try:
                persist_token(token, now.date(), env_path=ROOT / ".env", environ=os.environ)
            except Exception:
                log.error("새 Threads 토큰 저장 실패 — GH_PAT 또는 .env 확인 필요")
                exit_code = 3
            else:
                log.info("Threads 토큰 갱신 완료")

    client = ThreadsClient(s.threads_user_id, token)
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    try:
        if args.only in ("publish", "all"):
            run_publish(store, client, s.daily_cap, now, log, dry_run=args.dry_run)
        if args.only in ("collect", "all") and not args.dry_run:
            run_collect(store, client, now, log)
    except ThreadsError as e:
        if e.code == TOKEN_EXPIRED:
            log.error("Threads 토큰 만료 — uv run python -m channels.threads.get_token 으로 재발급 필요")
            return 2
        log.error("Threads API 오류: %s", e)
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
