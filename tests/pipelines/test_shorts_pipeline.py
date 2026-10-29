import io
import logging
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from channels.tts.google import Speech, Word
from channels.video.ffmpeg import VideoError, media_duration, run as ffmpeg
from channels.video.frames import FontError, find_font
from core.models import Post
from pipelines.shopping_shorts.__main__ import run
from pipelines.shopping_shorts.render import render_short
from test_shorts_script import BLOCKS, h2, para

POST = Post("page-1", "YT-틈새솔-1", "수익", "", None, "쿠팡 파트너스 활동으로 수수료를 받습니다", None)
LOG = logging.getLogger("test")


class Store:
    def __init__(self, posts, blocks):
        self.posts, self.blocks = posts, blocks
        self.failed, self.rendered = [], []

    def approved_shorts(self):
        return list(self.posts)

    def page_blocks(self, page_id):
        return self.blocks

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def mark_rendered(self, post):
        self.rendered.append(post.content_id)


def test_valid_page_rendered():
    store = Store([POST], BLOCKS)
    made = []
    assert run(store, lambda p, s: made.append(len(s)) or Path("x.mp4"), LOG) == 0
    assert made == [2] and store.rendered == ["YT-틈새솔-1"] and store.failed == []


def test_problems_mark_failed_without_render():
    store = Store([replace(POST, disclosure="")], BLOCKS)
    assert run(store, lambda p, s: pytest.fail("렌더하면 안 됨"), LOG) == 1
    assert store.failed == [("YT-틈새솔-1", "대가성문구 비어 있음")]


def test_render_error_marks_failed_and_continues():
    other = replace(POST, page_id="page-2", content_id="YT-2")
    calls = []

    def make(post, scenes):
        calls.append(post.content_id)
        if post.content_id == "YT-틈새솔-1":
            raise VideoError("ffmpeg 실패: boom")
        return Path("ok.mp4")

    store = Store([POST, other], BLOCKS)
    assert run(store, make, LOG) == 1
    assert calls == ["YT-틈새솔-1", "YT-2"]
    assert store.failed == [("YT-틈새솔-1", "render: ffmpeg 실패: boom")]
    assert store.rendered == ["YT-2"]


def test_dry_run_and_content_id_filter_touch_nothing():
    store = Store([POST, replace(POST, content_id="YT-2")], [h2("장면 1 · 카드"), para("화면: 필수템")])
    assert run(store, lambda p, s: pytest.fail("렌더 X"), LOG, dry_run=True, content_id="YT-2") == 0
    assert store.failed == [] and store.rendered == []


try:
    FONT = find_font({})
except FontError:
    FONT = None


class FakeTTS:
    """무음 mp3 + 단어 시각 (0.25초 간격)."""

    def __init__(self, tmp: Path):
        self.tmp, self.texts = tmp, []

    def synthesize(self, text, voice, rate=1.0):
        self.texts.append(text)
        words = text.split()
        mp3 = self.tmp / f"tts{len(self.texts)}.mp3"
        end = 0.25 * len(words)
        ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(end), "-c:a", "libmp3lame", str(mp3)])
        return Speech(mp3.read_bytes(), [Word(w, 0.25 * i) for i, w in enumerate(words)], end)


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_render_short_end_to_end(tmp_path):
    from pipelines.shopping_shorts.script import parse_scenes

    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (240, 200, 160)).save(buf, "PNG")
    fetched = []
    tts = FakeTTS(tmp_path)
    out = render_short(parse_scenes(BLOCKS), POST.disclosure, tts=tts,
                       fetch=lambda url: fetched.append(url) or buf.getvalue(),
                       work=tmp_path / "work", out=tmp_path / "short.mp4", font=FONT, voice="v", rate=1.0)
    assert fetched == ["https://s3/1.png"]
    assert tts.texts[-1] == "제품 정보는 프로필 링크에서 확인하세요."
    expected = sum(0.25 * len(t.split()) + 0.4 for t in tts.texts)
    assert media_duration(out) == pytest.approx(expected, abs=0.3)
