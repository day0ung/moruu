"""python -m pipelines.ai_story plan --series 이름 [--topic 소재]
python -m pipelines.ai_story write [--content-id ID]

plan : 시리즈 바이블·지난 회차 요약으로 기획안 3개 → 콘텐츠 DB 페이지 3개 (status=기획). 사람이 하나를 기획승인으로.
write: status=기획승인 글마다 챕터별 작성 → 검수(최대 3회 수정) → 그림 프롬프트 → 페이지에 붙임 → 회차 요약 → DRAFT.
       한도에 걸리면 멈추고(상태 그대로) 다음 실행 때 이어서 쓴다. 형식·설계: docs/superpowers/specs/2026-10-30-ai-story-agent-design.md
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from channels.llm.client import LLM, LLMError, LLMQuotaError
from channels.telegram.client import Telegram
from core import schema as S
from core.config import ConfigError, DramaSettings, LLMSettings, TelegramSettings
from core.log import setup_logging
from core.models import KST, Post
from core.notion_store import DbIds, NotionStore
from pipelines.ai_story import agents
from pipelines.ai_story.agents import Chapter
from pipelines.ai_story.checks import CHARS_PER_MIN, chapter_target, spoken_chars
from pipelines.ai_story.context import load_series
from pipelines.ai_story.doc import (PLAN_TOGGLE, REVIEW_TOGGLE, chapter_blocks, find_toggle, para, plain, plan_blocks,
                                    read_plan, scenes_text, toggle, written)

ROOT = Path(__file__).resolve().parents[2]
MUSIC_TAGS = ["잔잔", "슬픔", "긴장", "따뜻함"]
_PAGE_ID = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f-]{36}$")


def _tail(text: str, n: int = 1200) -> str:
    return text[-n:]


def run_plan(store, llm, series_name: str, topic: str, log: logging.Logger, notify: Callable[[str], object],
             now: datetime, count: int = 3, minutes: int = 30) -> int:
    series_id = store.find_series(series_name) or (series_name if _PAGE_ID.match(series_name) else None)
    if not series_id:
        log.error("시리즈 '%s' 없음 (📚 시리즈 DB 의 이름)", series_name)
        return 1
    series = load_series(store, series_id)
    plans = agents.plan(llm, series, topic, count=count, minutes=minutes)
    if not plans:
        notify(f"❌ 기획 실패 · {series_name}: 기획안을 못 받음")
        return 1
    for i, p in enumerate(plans, 1):
        cid = f"YT-롱폼-{now:%Y%m%d-%H%M}-{i}"
        props = {S.TITLE_ID: S.title(cid), S.CHANNEL: S.select(S.CH_YT_LONG), S.STATUS: S.select(S.PLAN),
                 S.SERIES: S.relation([series_id]), S.MEMO: S.rich(topic or (p.get("titles") or [""])[0])}
        store.create_page(props, plan_blocks(p))
        log.info("기획안 %s: %s", cid, (p.get("titles") or ["?"])[0])
    notify(f"📝 기획안 {len(plans)}개 · {series_name} — " + " / ".join((p.get("titles") or ["?"])[0] for p in plans)
           + " → 하나를 기획승인으로")
    return 0


def _script_from(blocks: list[dict]) -> str:
    """첫 챕터 제목부터 끝까지 대사 문단 글자."""
    started, out = False, []
    for b in blocks:
        if b.get("type") == "heading_1":
            started = True
        elif started and b.get("type") == "paragraph":
            out.append(plain(b))
    return "\n".join(out)


def write_one(store, llm, post: Post, log: logging.Logger, minutes: int, music: list[str]) -> tuple[int, int]:
    """(새로 쓴 챕터 수, 전체 글자 수). 실패는 예외로."""
    blocks = store.page_blocks(post.page_id)
    plan_id = find_toggle(blocks, PLAN_TOGGLE)
    if not plan_id:
        raise ValueError(f"'{PLAN_TOGGLE}' 토글 없음")
    plan_text = read_plan(store.page_blocks(plan_id))
    if not plan_text.chapters:
        raise ValueError("기획안에 '### 챕터 N · 제목' 이 없음")
    series = load_series(store, post.series, exclude_page=post.page_id)
    rows = series.new_rows(plan_text.characters)
    if rows and series.table_id:
        store.add_table_rows(series.table_id, rows)
        log.info("바이블에 인물 추가: %s", ", ".join(r[0] for r in rows if r))

    done, next_scene = written(blocks)
    review_id = find_toggle(blocks, REVIEW_TOGGLE) or store.append_blocks(post.page_id, [toggle(REVIEW_TOGGLE, [])])[0]["id"]
    previous = _tail(_script_from(blocks))
    total = len(plan_text.chapters)
    target = chapter_target(minutes, total)
    for idx in range(done, total):
        title, beats = plan_text.chapters[idx]
        ch = Chapter(idx + 1, total, title, beats)
        scenes, note = agents.write_reviewed(llm, series, plan_text, ch, previous, target, music)
        for s, image in zip(scenes, agents.image_prompts(llm, series, scenes)):
            s["image_prompt"] = image
        store.append_blocks(post.page_id, chapter_blocks(ch.number, title, scenes, next_scene))
        store.append_blocks(review_id, [para(f"{note} · {spoken_chars(scenes)}자")])
        next_scene += len(scenes)
        previous = _tail(scenes_text(scenes))
        log.info("%s %s", post.content_id, note)

    script = _script_from(store.page_blocks(post.page_id))
    store.mark_written(post, agents.summarize(llm, plan_text, script))
    return total - done, len(re.sub(r"\s", "", script))


def run_write(store, llm, log: logging.Logger, notify: Callable[[str], object], content_id: str | None = None,
              minutes: int = 30, music: list[str] = MUSIC_TAGS) -> int:
    posts = [p for p in store.approved_plans() if not content_id or p.content_id == content_id]
    if not posts:
        log.info("대본을 쓸 글 없음 (채널=YT-롱폼, status=기획승인)")
        return 0
    failed = 0
    for post in posts:
        if not post.series:
            failed += 1
            store.mark_failed(post, "story: 시리즈 연결 없음")
            notify(f"❌ {post.content_id} 대본 실패 · 시리즈 연결 없음")
            continue
        try:
            new, chars = write_one(store, llm, post, log, minutes, music)
        except LLMQuotaError as e:
            failed += 1
            log.warning("%s 한도로 멈춤: %s", post.content_id, e)
            notify(f"⏸ {post.content_id} AI 한도로 멈춤 — 다음 실행 때 이어서 씀 ({str(e)[:200]})")
            continue
        except (LLMError, ValueError, httpx.HTTPError) as e:
            failed += 1
            log.error("%s 대본 실패: %s", post.content_id, e)
            store.mark_failed(post, f"story: {e}")
            notify(f"❌ {post.content_id} 대본 실패 · {str(e)[:300]}")
            continue
        notify(f"✍️ {post.content_id} 대본 DRAFT · 챕터 {new}개 새로 씀 · 약 {chars:,}자 ≈ {chars / CHARS_PER_MIN:.0f}분"
               " → Notion 에서 검토 후 APPROVED")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ai_story")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="기획안 3개")
    p.add_argument("--series", required=True, help="📚 시리즈 DB 의 이름 (또는 페이지 ID)")
    p.add_argument("--topic", default="", help="소재 한 줄 (비우면 자유)")
    w = sub.add_parser("write", help="기획승인 글의 대본")
    w.add_argument("--content-id", help="이 content_id 만")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = DramaSettings.from_env(os.environ, need_tts=False)
        llm_cfg = LLMSettings.from_env(os.environ)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    if not llm_cfg.providers:
        print("AI 키 없음 — .env 에 GEMINI_API_KEY 또는 OPENROUTER_API_KEY", file=sys.stderr)
        return 1
    series_db = os.environ.get("NOTION_DB_SERIES", "")
    if args.cmd == "plan" and not series_db:
        print("NOTION_DB_SERIES 가 필요합니다 (📚 시리즈 DB ID)", file=sys.stderr)
        return 1
    tg = TelegramSettings.from_env(os.environ)
    log = setup_logging([s.notion_token, *(pv.key for pv in llm_cfg.providers), tg.token if tg else ""])
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures,
                                              series=series_db))
    llm = LLM(llm_cfg.providers)
    notify = Telegram(tg.token, tg.chat_id).send if tg else (lambda text: log.info("알림: %s", text))
    minutes = int(os.environ.get("STORY_MINUTES") or 30)
    if args.cmd == "plan":
        return run_plan(store, llm, args.series, args.topic, log, notify, datetime.now(KST), minutes=minutes)
    music = [t.strip() for t in (os.environ.get("STORY_MUSIC_TAGS") or ",".join(MUSIC_TAGS)).split(",") if t.strip()]
    return run_write(store, llm, log, notify, args.content_id, minutes, music)


if __name__ == "__main__":
    sys.exit(main())
