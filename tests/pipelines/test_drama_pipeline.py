import logging
from dataclasses import replace
from pathlib import Path

import pytest

from channels.tts.google import TTSError
from channels.video.ffmpeg import VideoError
from core.models import Post
from core.notion_store import Table
from pipelines.ai_drama.__main__ import run

LOG = logging.getLogger("test")
POST = Post("page-1", "YT-롱폼-1", "", "", None, "", None, series="series-1")
BIBLE = [Table([["인물", "목소리"], ["내레이션", "N"], ["아들", "S"]], True)]


def rt(text):
    return [{"plain_text": text, "annotations": {}}]


BLOCKS = [{"type": "heading_2", "heading_2": {"rich_text": rt("장면 1 #음악 잔잔")}},
          {"type": "paragraph", "paragraph": {"rich_text": rt("그날 저녁.\n아들: 다녀왔어요.")}}]


class Store:
    def __init__(self, posts, blocks=BLOCKS, bible=BIBLE):
        self.posts, self.blocks, self.bible = posts, blocks, bible
        self.failed, self.rendered = [], []

    def approved_drama(self):
        return list(self.posts)

    def page_blocks(self, page_id):
        return self.blocks

    def tables(self, page_id):
        assert page_id == "series-1"
        return self.bible

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def mark_rendered(self, post, link=None):
        self.rendered.append((post.content_id, link))


@pytest.fixture
def media(tmp_path):
    for cid in ("YT-롱폼-1", "YT-롱폼-2"):
        ep = tmp_path / "assets" / cid
        ep.mkdir(parents=True)
        (ep / "01.png").write_bytes(b"x")
        (ep / "출처.txt").write_text("AI:Gemini\n", encoding="utf-8")
    music = tmp_path / "music"
    music.mkdir()
    (music / "잔잔.mp3").write_bytes(b"x")
    (music / "출처.txt").write_text("잔잔: YouTube 오디오 보관함\n", encoding="utf-8")
    return {"assets": tmp_path / "assets", "music_dir": music}


def test_renders_and_marks_rendered(media):
    seen = {}

    def build(post, scenes, cast, music):
        seen.update(lines=[x.speaker for x in scenes[0].lines], music=music, cast=sorted(cast))
        return "TL"

    store = Store([POST])
    assert run(store, build, lambda p, tl: Path("ep.mp4"), LOG, **media) == 0
    assert seen == {"lines": ["내레이션", "아들"], "music": {"잔잔": media["music_dir"] / "잔잔.mp3"},
                    "cast": ["내레이션", "아들"]}
    assert store.rendered == [("YT-롱폼-1", None)] and store.failed == []


def test_uploader_link_and_notifier(media):
    sent = []
    store = Store([POST])
    run(store, lambda *a: "TL", lambda p, tl: Path("ep.mp4"), LOG,
        uploader=lambda p, path: "https://drive/1", notifier=sent.append, **media)
    assert store.rendered == [("YT-롱폼-1", "https://drive/1")]
    assert sent == ["✅ YT-롱폼-1 렌더 완료 · https://drive/1"]


def test_problems_mark_failed(media):
    sent = []
    store = Store([replace(POST, series="")])
    assert run(store, lambda *a: pytest.fail("X"), lambda *a: pytest.fail("X"), LOG, notifier=sent.append,
               **media) == 1
    assert store.failed == [("YT-롱폼-1", "시리즈 연결 없음; 장면 1: 인물 '아들' 바이블에 없음")]
    assert sent[0].startswith("❌ YT-롱폼-1 실패 · 시리즈 연결 없음")


def test_errors_prefixed_and_continue(media):
    other = replace(POST, page_id="p2", content_id="YT-롱폼-2")

    def build(post, *a):
        if post.content_id == "YT-롱폼-1":
            raise TTSError("429", "quota")
        return "TL"

    def render(post, tl):
        raise VideoError("장면 1: boom")

    def upload(post, path):
        raise AssertionError("업로드 X")

    store = Store([POST, other])
    assert run(store, build, render, LOG, uploader=upload, **media) == 1
    assert store.failed == [("YT-롱폼-1", "tts: [429] quota"), ("YT-롱폼-2", "render: 장면 1: boom")]


def test_upload_error(media):
    def upload(post, path):
        raise OSError("disk")

    store = Store([POST])
    assert run(store, lambda *a: "TL", lambda p, tl: Path("ep.mp4"), LOG, uploader=upload, **media) == 1
    assert store.failed == [("YT-롱폼-1", "upload: disk")]


def test_dry_run_touches_nothing(media):
    store = Store([POST, replace(POST, content_id="YT-롱폼-9")])
    assert run(store, None, lambda *a: pytest.fail("X"), LOG, dry_run=True, content_id="YT-롱폼-1", **media) == 0
    assert store.failed == [] and store.rendered == []


def test_fetch_media_error(media):
    from channels.gdrive.client import DriveError

    def fetch(post):
        raise DriveError(403, "x")

    store = Store([POST])
    assert run(store, lambda *a: pytest.fail("X"), lambda *a: pytest.fail("X"), LOG, fetch_media=fetch, **media) == 1
    assert store.failed == [("YT-롱폼-1", "drive: [403] x")]
