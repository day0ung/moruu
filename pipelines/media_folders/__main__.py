"""python -m pipelines.media_folders

쇼츠·롱폼 글(DRAFT·APPROVED) 중 `자료 폴더` 가 빈 것마다 Drive 에 moruu/{쇼츠|롱폼}/{content_id}/ 를 만들고
링크를 Notion `자료 폴더` 에 적는다. 상태는 바꾸지 않는다. 필요: .env 의 GDRIVE_* (docs/TODO-manual.md 6-4).
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from dotenv import load_dotenv

from channels.gdrive.client import DriveClient, DriveError, folder_url
from channels.gdrive.sync import folder_path
from channels.telegram.client import Telegram
from core.config import ConfigError, DriveSettings, ShortsSettings, TelegramSettings
from core.log import setup_logging
from core.models import Post
from core.notion_store import DbIds, NotionStore

ROOT = Path(__file__).resolve().parents[2]
CHANNEL_DIR = {"YT-쇼핑": "쇼츠", "YT-롱폼": "롱폼"}


def run(store, make_folder: Callable[[Post], str], log: logging.Logger,
        notifier: Callable[[str], None] | None = None) -> int:
    notify = notifier or (lambda text: log.info("알림: %s", text))
    posts = store.missing_media_folders()
    if not posts:
        log.info("자료 폴더를 만들 글 없음")
        return 0
    made, failed = 0, []
    for post in posts:
        try:
            url = make_folder(post)
        except (DriveError, httpx.HTTPError) as e:
            log.warning("%s 폴더 실패: %s", post.content_id, e)
            failed.append(f"{post.content_id}: {e}")
            continue
        store.set_media_folder(post, url)
        made += 1
        log.info("%s 자료 폴더: %s", post.content_id, url)
    notify(f"📁 자료 폴더 {made}개 만듦" + (f" · 실패 {len(failed)}개 ({'; '.join(failed)[:300]})" if failed else ""))
    return 1 if failed else 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        s = ShortsSettings.from_env(os.environ, need_tts=False)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    drive_cfg = DriveSettings.from_env(os.environ)
    if drive_cfg is None:
        print("GDRIVE_CLIENT_ID / SECRET / REFRESH_TOKEN / ROOT_ID 가 필요합니다", file=sys.stderr)
        return 1
    tg = TelegramSettings.from_env(os.environ)
    log = setup_logging([s.notion_token, drive_cfg.client_secret, drive_cfg.refresh_token, tg.token if tg else ""])
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    drive = DriveClient(drive_cfg.client_id, drive_cfg.client_secret, drive_cfg.refresh_token)

    def make_folder(post: Post) -> str:
        return folder_url(folder_path(drive, drive_cfg.root_id, CHANNEL_DIR[post.channel], post.content_id))

    notifier = Telegram(tg.token, tg.chat_id).send if tg else None
    return run(store, make_folder, log, notifier)


if __name__ == "__main__":
    sys.exit(main())
