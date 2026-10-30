"""python -m pipelines.shopping_shorts [--dry-run] [--content-id ID] [--from-drive] [--no-upload]

Notion 콘텐츠 DB 의 채널=YT-쇼핑, status=APPROVED 페이지 → out/shorts/{content_id}.mp4 → status=RENDERED.
화면 파일은 Notion 이미지 또는 assets/shorts/{content_id}/01.png … (출처는 같은 폴더 출처.txt).
--dry-run: 본문 파싱·검사 결과만 출력 (Notion 은 읽기만, TTS 키 불필요).
--from-drive: 렌더 전에 Drive moruu/쇼츠/{content_id}/ 를 assets/shorts/{content_id}/ 로 받는다 (GDRIVE_* 필요).
Drive 설정이 있으면 결과 mp4 를 같은 Drive 폴더에 올리고(--no-upload 면 안 함), 텔레그램 설정이 있으면 알린다.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from dotenv import load_dotenv

from channels.gdrive.client import DriveError
from channels.gdrive.cloud import Cloud
from channels.telegram.client import Telegram
from channels.tts import narration
from channels.tts.google import GoogleTTS, TTSError
from channels.video.ffmpeg import VideoError
from channels.video.frames import FontError, find_font
from core.config import ConfigError, DriveSettings, ShortsSettings, TelegramSettings
from core.log import setup_logging
from core.models import Post
from core.notion_store import DbIds, NotionStore
from pipelines.shopping_shorts.render import LINE_MAX, render_short
from pipelines.shopping_shorts.script import Cut, attach_folder, parse_cuts, script_problems

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "shorts"
ASSETS = ROOT / "assets" / "shorts"
RENDER_ERRORS = (TTSError, VideoError, FontError, httpx.HTTPError, OSError, ValueError)


def run(store, make_video: Callable[[Post, list[Cut]], Path], log: logging.Logger,
        dry_run: bool = False, content_id: str | None = None, assets: Path = ASSETS, *,
        fetch_media: Callable[[Post], object] | None = None, uploader: Callable[[Post, Path], str] | None = None,
        notifier: Callable[[str], object] | None = None) -> int:
    """fetch_media(post): 검사 전에 자료 받기. uploader(post, mp4) → 링크. notifier(글): 결과 알림 (없으면 로그)."""
    notify = notifier or (lambda text: log.info("알림: %s", text))
    posts = [p for p in store.approved_shorts() if not content_id or p.content_id == content_id]
    if not posts:
        log.info("렌더할 쇼츠 없음 (채널=YT-쇼핑, status=APPROVED)")
        return 0
    failed = 0

    def fail(post: Post, reason: str) -> None:
        nonlocal failed
        failed += 1
        log.warning("%s 실패: %s", post.content_id, reason)
        store.mark_failed(post, reason)
        notify(f"❌ {post.content_id} 실패 · {reason[:300]}")

    for post in posts:
        if fetch_media:
            try:
                fetch_media(post)
            except (DriveError, httpx.HTTPError, OSError) as e:
                if dry_run:
                    log.warning("[dry-run] %s 자료 받기 실패: %s", post.content_id, e)
                else:
                    fail(post, f"drive: {e}")
                continue
        cuts = parse_cuts(store.page_blocks(post.page_id))
        problems = attach_folder(cuts, assets / post.content_id) + script_problems(cuts, post.disclosure)
        if dry_run:
            log.info("[dry-run] %s — 컷 %d개", post.content_id, len(cuts))
            for c in cuts:
                screen = c.image_path.name if c.image_path else c.kind
                log.info("  컷 %d · %s%s%s | 화면 문구: %s", c.number, screen, f" #{c.voice}" if c.voice else "",
                         f" #{c.seconds:g}초" if c.seconds else "", c.caption_text)
                for raw in c.lines:
                    for line in narration.to_lines(raw, {}, LINE_MAX):
                        log.info("    자막: %s", line.shown)
            for p in problems:
                log.warning("  문제: %s", p)
            continue
        if problems:
            fail(post, "; ".join(problems))
            continue
        try:
            path = make_video(post, cuts)
        except RENDER_ERRORS as e:
            fail(post, f"render: {e}")
            continue
        try:
            link = uploader(post, path) if uploader else None
        except (DriveError, httpx.HTTPError, OSError) as e:
            fail(post, f"upload: {e}")
            continue
        store.mark_rendered(post, link)
        log.info("%s 완료: %s", post.content_id, path)
        notify(f"✅ {post.content_id} 렌더 완료 · {link or path}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shopping_shorts")
    ap.add_argument("--dry-run", action="store_true", help="렌더하지 않고 파싱·검사 결과만 출력")
    ap.add_argument("--content-id", help="이 content_id 만")
    ap.add_argument("--from-drive", action="store_true", help="렌더 전에 Drive 자료 폴더를 받는다")
    ap.add_argument("--no-upload", action="store_true", help="Drive 에 결과를 올리지 않는다")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = ShortsSettings.from_env(os.environ, need_tts=not args.dry_run)
        font = None if args.dry_run else find_font()
    except (ConfigError, FontError) as e:
        print(e, file=sys.stderr)
        return 1
    drive_cfg, tg = DriveSettings.from_env(os.environ), TelegramSettings.from_env(os.environ)
    if args.from_drive and drive_cfg is None:
        print("--from-drive: GDRIVE_CLIENT_ID / SECRET / REFRESH_TOKEN / ROOT_ID 가 필요합니다", file=sys.stderr)
        return 1
    log = setup_logging([s.notion_token, s.tts_key, drive_cfg.client_secret if drive_cfg else "",
                         drive_cfg.refresh_token if drive_cfg else "", tg.token if tg else ""])
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    cloud = Cloud(drive_cfg, "쇼츠") if drive_cfg else None
    lexicon = store.lexicon(s.lexicon_page) if s.lexicon_page and not args.dry_run else {}
    tts = GoogleTTS(s.tts_key)
    files = httpx.Client(timeout=60, follow_redirects=True)  # Notion 파일 주소(S3) — Notion 토큰을 보내지 않는다

    def fetch(url: str) -> bytes:
        r = files.get(url)
        r.raise_for_status()
        return r.content

    def make_video(post: Post, cuts: list[Cut]) -> Path:
        return render_short(cuts, post.disclosure, tts=tts, fetch=fetch, work=OUT / post.content_id,
                            out=OUT / f"{post.content_id}.mp4", font=font,
                            voices={"여": s.tts_voice, "남": s.tts_voice_male},
                            default_voice=post.voice if post.voice in ("여", "남") else "여",
                            rate=s.tts_rate, lexicon=lexicon)

    fetch_media = (lambda post: cloud.fetch(post.content_id, ASSETS / post.content_id)) if args.from_drive else None
    uploader = (lambda post, path: cloud.upload(post.content_id, [path]))         if cloud and not args.no_upload and not args.dry_run else None
    notifier = Telegram(tg.token, tg.chat_id).send if tg and not args.dry_run else None
    return run(store, make_video, log, dry_run=args.dry_run, content_id=args.content_id,
               fetch_media=fetch_media, uploader=uploader, notifier=notifier)


if __name__ == "__main__":
    sys.exit(main())
