"""python -m pipelines.shopping_shorts [--dry-run] [--content-id ID]

Notion 콘텐츠 DB 의 채널=YT-쇼핑, status=APPROVED 페이지 → out/shorts/{content_id}.mp4 → status=RENDERED.
--dry-run: 본문 파싱·검사 결과만 출력 (Notion 은 읽기만, TTS 키 불필요).
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

from channels.tts.google import GoogleTTS, TTSError
from channels.video.ffmpeg import VideoError
from channels.video.frames import FontError, find_font
from core.config import ConfigError, ShortsSettings
from core.log import setup_logging
from core.models import Post
from core.notion_store import DbIds, NotionStore
from pipelines.shopping_shorts.render import render_short
from pipelines.shopping_shorts.script import Scene, parse_scenes, script_problems

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "shorts"
RENDER_ERRORS = (TTSError, VideoError, FontError, httpx.HTTPError, OSError, ValueError)


def run(store, make_video: Callable[[Post, list[Scene]], Path], log: logging.Logger,
        dry_run: bool = False, content_id: str | None = None) -> int:
    posts = [p for p in store.approved_shorts() if not content_id or p.content_id == content_id]
    if not posts:
        log.info("렌더할 쇼츠 없음 (채널=YT-쇼핑, status=APPROVED)")
        return 0
    failed = 0
    for post in posts:
        scenes = parse_scenes(store.page_blocks(post.page_id))
        problems = script_problems(scenes, post.disclosure)
        if dry_run:
            log.info("[dry-run] %s — 장면 %d개", post.content_id, len(scenes))
            for s in scenes:
                log.info("  장면 %d · %s | 화면: %s | 내레이션: %s", s.number, s.kind, s.caption_text, s.narration)
            for p in problems:
                log.warning("  문제: %s", p)
            continue
        if problems:
            failed += 1
            log.warning("%s 검사 실패: %s", post.content_id, "; ".join(problems))
            store.mark_failed(post, "; ".join(problems))
            continue
        try:
            path = make_video(post, scenes)
        except RENDER_ERRORS as e:
            failed += 1
            log.error("%s 렌더 실패: %s", post.content_id, e)
            store.mark_failed(post, f"render: {e}")
            continue
        store.mark_rendered(post)
        log.info("%s 완료: %s", post.content_id, path)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shopping_shorts")
    ap.add_argument("--dry-run", action="store_true", help="렌더하지 않고 파싱·검사 결과만 출력")
    ap.add_argument("--content-id", help="이 content_id 만")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = ShortsSettings.from_env(os.environ, need_tts=not args.dry_run)
        font = None if args.dry_run else find_font()
    except (ConfigError, FontError) as e:
        print(e, file=sys.stderr)
        return 1
    log = setup_logging([s.notion_token, s.tts_key])
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    tts = GoogleTTS(s.tts_key)
    files = httpx.Client(timeout=60, follow_redirects=True)  # Notion 파일 주소(S3) — Notion 토큰을 보내지 않는다

    def fetch(url: str) -> bytes:
        r = files.get(url)
        r.raise_for_status()
        return r.content

    def make_video(post: Post, scenes: list[Scene]) -> Path:
        return render_short(scenes, post.disclosure, tts=tts, fetch=fetch, work=OUT / post.content_id,
                            out=OUT / f"{post.content_id}.mp4", font=font, voice=s.tts_voice, rate=s.tts_rate)

    return run(store, make_video, log, dry_run=args.dry_run, content_id=args.content_id)


if __name__ == "__main__":
    sys.exit(main())
