"""python -m pipelines.ai_drama [--dry-run] [--content-id ID]

Notion 콘텐츠 DB 의 채널=YT-롱폼, status=APPROVED 페이지 → out/drama/{content_id}.mp4 · .srt · .timeline.json
→ status=RENDERED. 인물·목소리는 연결된 시리즈 페이지의 바이블 표, 그림은 assets/longform/{content_id}/01.png …,
음악은 assets/music/{태그}.mp3 (형식: docs/notion-schema.md).
--dry-run: 검사 + (TTS 키가 있으면) 장면별 길이만. 렌더·상태 변경 없음. TTS 결과는 .cache/tts 에 남아 재사용된다.
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

from channels.tts.cache import CachedTTS
from channels.tts.google import GoogleTTS, TTSError
from channels.video.ffmpeg import VideoError
from channels.video.frames import FontError, find_font
from channels.video.render import render as render_timeline
from channels.video.timeline import Timeline
from core.config import ConfigError, DramaSettings
from core.log import setup_logging
from core.models import Post
from core.notion_store import DbIds, NotionStore
from pipelines.ai_drama.bible import parse_bible
from pipelines.ai_drama.build import build_timeline
from pipelines.ai_drama.script import attach_images, find_music, parse_episode, script_problems

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "drama"
ASSETS = ROOT / "assets" / "longform"
MUSIC = ROOT / "assets" / "music"
CACHE = ROOT / ".cache" / "tts"
STEP_ERRORS = (TTSError, VideoError, FontError, httpx.HTTPError, OSError, ValueError)


def _clock(sec: float) -> str:
    m, s = divmod(round(sec), 60)
    return f"{m}분 {s:02}초"


def run(store, build: Callable | None, render: Callable[[Post, Timeline], Path], log: logging.Logger, *,
        dry_run: bool = False, content_id: str | None = None, assets: Path = ASSETS, music_dir: Path = MUSIC,
        default_rate: float = 1.0, uploader: Callable[[Post, Path], str] | None = None,
        notifier: Callable[[str], None] | None = None) -> int:
    """build(post, scenes, cast, music) → Timeline, render(post, timeline) → mp4 경로.
    uploader(post, path) → 링크 (없으면 업로드 안 함), notifier(글) (없으면 로그로)."""
    notify = notifier or (lambda text: log.info("알림: %s", text))
    posts = [p for p in store.approved_drama() if not content_id or p.content_id == content_id]
    if not posts:
        log.info("렌더할 롱폼 없음 (채널=YT-롱폼, status=APPROVED)")
        return 0
    failed = 0
    for post in posts:
        problems: list[str] = []
        if post.series:
            cast, bible_problems = parse_bible([t.rows for t in store.tables(post.series)], default_rate)
            problems += bible_problems
        else:
            cast = {}
            problems.append("시리즈 연결 없음")
        scenes, parse_problems = parse_episode(store.page_blocks(post.page_id), set(cast))
        problems += parse_problems + attach_images(scenes, assets / post.content_id) + script_problems(scenes)
        music, music_problems = find_music({s.music for s in scenes if s.music}, music_dir)
        problems += music_problems

        if dry_run:
            log.info("[dry-run] %s — 장면 %d개", post.content_id, len(scenes))
            for p in problems:
                log.warning("  문제: %s", p)
            if build and not problems:
                tl = build(post, scenes, cast, music)
                for s in tl.scenes:
                    log.info("  장면 %d · %s %s (%d줄)", s.number, s.title, _clock(s.duration), len(s.clips))
                log.info("  전체 %s", _clock(tl.total))
            continue
        if problems:
            failed += 1
            log.warning("%s 검사 실패: %s", post.content_id, "; ".join(problems))
            store.mark_failed(post, "; ".join(problems))
            notify(f"❌ {post.content_id} 실패 · {'; '.join(problems)[:300]}")
            continue

        step = "tts"
        try:
            timeline = build(post, scenes, cast, music)
            step = "render"
            path = render(post, timeline)
            step = "upload"
            link = uploader(post, path) if uploader else None
        except STEP_ERRORS as e:
            failed += 1
            log.error("%s %s 실패: %s", post.content_id, step, e)
            store.mark_failed(post, f"{step}: {e}")
            notify(f"❌ {post.content_id} 실패 · {step}: {str(e)[:300]}")
            continue
        store.mark_rendered(post, link)
        log.info("%s 완료: %s", post.content_id, path)
        notify(f"✅ {post.content_id} 렌더 완료 · {link or path}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ai_drama")
    ap.add_argument("--dry-run", action="store_true", help="렌더하지 않고 검사·길이만 출력")
    ap.add_argument("--content-id", help="이 content_id 만")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = DramaSettings.from_env(os.environ, need_tts=not args.dry_run)
        font = None if args.dry_run else find_font()
    except (ConfigError, FontError) as e:
        print(e, file=sys.stderr)
        return 1
    log = setup_logging([s.notion_token, s.tts_key])
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    lexicon = store.lexicon(s.lexicon_page) if s.lexicon_page else {}
    tts = CachedTTS(GoogleTTS(s.tts_key), CACHE) if s.tts_key else None

    def build(post: Post, scenes, cast, music) -> Timeline:
        tl = build_timeline(scenes, cast, tts, lexicon, OUT / post.content_id, music)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{post.content_id}.timeline.json").write_text(tl.to_json(), encoding="utf-8")
        return tl

    def render(post: Post, timeline: Timeline) -> Path:
        return render_timeline(timeline, OUT / post.content_id, OUT / f"{post.content_id}.mp4", font)

    return run(store, build if tts else None, render, log, dry_run=args.dry_run, content_id=args.content_id,
               default_rate=s.tts_rate)


if __name__ == "__main__":
    sys.exit(main())
