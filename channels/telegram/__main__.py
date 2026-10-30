"""python -m channels.telegram "글"   — 시험 알림
python -m channels.telegram --chat-id  — 봇에게 마지막으로 말 건 대화방 ID 를 .env 의 TELEGRAM_CHAT_ID 로 저장"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import dotenv_values

from channels.telegram.client import Telegram
from channels.threads.token import update_env_file

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="telegram")
    ap.add_argument("text", nargs="?", help="보낼 글")
    ap.add_argument("--chat-id", action="store_true", help="대화방 ID 를 .env 에 저장")
    args = ap.parse_args(argv)
    cfg = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    token = cfg.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN 값이 비어 있습니다 (.env 확인)")
        return 1
    if args.chat_id:
        chat = Telegram(token, "").latest_chat_id()
        if not chat:
            print("대화방을 못 찾음 — 봇 대화방에서 아무 메시지나 보낸 뒤 다시 실행")
            return 1
        update_env_file(ENV_PATH, {"TELEGRAM_CHAT_ID": chat})
        print("저장됨: TELEGRAM_CHAT_ID")
        return 0
    if not args.text or not cfg.get("TELEGRAM_CHAT_ID"):
        print("보낼 글과 TELEGRAM_CHAT_ID 가 필요합니다")
        return 1
    ok = Telegram(token, cfg["TELEGRAM_CHAT_ID"]).send(args.text)
    print("ok" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
