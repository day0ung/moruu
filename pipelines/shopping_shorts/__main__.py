"""python -m pipelines.shopping_shorts [--dry-run] [--content-id ID]

Notion 콘텐츠 DB 의 채널=YT-쇼핑, status=APPROVED 페이지 → out/shorts/{content_id}.mp4 → status=RENDERED.
화면 파일은 Notion 이미지 또는 assets/shorts/{content_id}/01.png … (출처는 같은 폴더 출처.txt).
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

from channels.tts import narration
from channels.tts.google import GoogleTTS, TTSError
from channels.video.ffmpeg import VideoError
from channels.video.frames import FontError, find_font
from core.config import ConfigError, ShortsSettings
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
        dry_run: bool = False, content_id: str | None = None, assets: Path = ASSETS) -> int:
    posts = [p for p in store.approved_shorts() if not content_id or p.content_id == content_id]
    if not posts:
        log.info("렌더할 쇼츠 없음 (채널=YT-쇼핑, status=APPROVED)")
        return 0
    failed = 0
    for post in posts:
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
            failed += 1
            log.warning("%s 검사 실패: %s", post.content_id, "; ".join(problems))
            store.mark_failed(post, "; ".join(problems))
            continue
        try:
            path = make_video(post, cuts)
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

    return run(store, make_video, log, dry_run=args.dry_run, content_id=args.content_id)


if __name__ == "__main__":
    sys.exit(main())
