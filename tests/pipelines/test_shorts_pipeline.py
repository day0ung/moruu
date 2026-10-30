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
from test_shorts_script import BLOCKS, para, quote

POST = Post("page-1", "YT-틈새솔-1", "수익", "", None, "쿠팡 파트너스 활동으로 수수료를 받습니다", None)
LOG = logging.getLogger("test")


class Store:
    def __init__(self, posts, blocks):
        self.posts, self.blocks = posts, blocks
        self.failed, self.rendered, self.links = [], [], []

    def approved_shorts(self):
        return list(self.posts)

    def page_blocks(self, page_id):
        return self.blocks

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def mark_rendered(self, post, link=None):
        self.rendered.append(post.content_id)
        self.links.append(link)


def test_valid_page_rendered(tmp_path):
    store = Store([POST], BLOCKS)
    made = []
    assert run(store, lambda p, s: made.append(len(s)) or Path("x.mp4"), LOG, assets=tmp_path) == 0
    assert made == [2] and store.rendered == ["YT-틈새솔-1"] and store.failed == []


def test_folder_problems_mark_failed(tmp_path):
    (tmp_path / POST.content_id).mkdir()
    (tmp_path / POST.content_id / "02.png").write_bytes(b"x")
    store = Store([POST], BLOCKS)
    assert run(store, lambda p, s: pytest.fail("렌더 X"), LOG, assets=tmp_path) == 1
    assert store.failed == [("YT-틈새솔-1", "컷 2: 02.png 출처 없음 — 출처.txt 에 적기")]


def test_problems_mark_failed_without_render(tmp_path):
    store = Store([replace(POST, disclosure="")], BLOCKS)
    assert run(store, lambda p, s: pytest.fail("렌더하면 안 됨"), LOG, assets=tmp_path) == 1
    assert store.failed == [("YT-틈새솔-1", "대가성문구 비어 있음")]


def test_render_error_marks_failed_and_continues(tmp_path):
    other = replace(POST, page_id="page-2", content_id="YT-2")
    calls = []

    def make(post, scenes):
        calls.append(post.content_id)
        if post.content_id == "YT-틈새솔-1":
            raise VideoError("ffmpeg 실패: boom")
        return Path("ok.mp4")

    store = Store([POST, other], BLOCKS)
    assert run(store, make, LOG, assets=tmp_path) == 1
    assert calls == ["YT-틈새솔-1", "YT-2"]
    assert store.failed == [("YT-틈새솔-1", "render: ffmpeg 실패: boom")]
    assert store.rendered == ["YT-2"]


def test_dry_run_and_content_id_filter_touch_nothing(tmp_path):
    store = Store([POST, replace(POST, content_id="YT-2")], [quote("필수템")])
    assert run(store, lambda p, s: pytest.fail("렌더 X"), LOG, dry_run=True, content_id="YT-2", assets=tmp_path) == 0
    assert store.failed == [] and store.rendered == []


def test_upload_link_and_notify(tmp_path):
    sent = []
    store = Store([POST], BLOCKS)
    assert run(store, lambda p, s: Path("x.mp4"), LOG, assets=tmp_path,
               uploader=lambda p, path: "https://drive/v", notifier=sent.append) == 0
    assert store.links == ["https://drive/v"]
    assert sent == ["✅ YT-틈새솔-1 렌더 완료 · https://drive/v"]


def test_upload_error_marks_failed(tmp_path):
    def upload(p, path):
        raise OSError("disk")

    sent = []
    store = Store([POST], BLOCKS)
    assert run(store, lambda p, s: Path("x.mp4"), LOG, assets=tmp_path, uploader=upload, notifier=sent.append) == 1
    assert store.failed == [("YT-틈새솔-1", "upload: disk")] and sent[0].startswith("❌ YT-틈새솔-1 실패 · upload: disk")


def test_fetch_media_error_marks_failed_without_render(tmp_path):
    from channels.gdrive.client import DriveError

    def fetch(post):
        raise DriveError(403, "x")

    store = Store([POST], BLOCKS)
    assert run(store, lambda p, s: pytest.fail("렌더 X"), LOG, assets=tmp_path, fetch_media=fetch) == 1
    assert store.failed == [("YT-틈새솔-1", "drive: [403] x")]


def test_fetch_media_runs_before_folder_check(tmp_path):
    def fetch(post):
        (tmp_path / post.content_id).mkdir()
        (tmp_path / post.content_id / "02.png").write_bytes(b"x")

    store = Store([POST], BLOCKS)
    run(store, lambda p, s: pytest.fail("렌더 X"), LOG, assets=tmp_path, fetch_media=fetch)
    assert store.failed == [("YT-틈새솔-1", "컷 2: 02.png 출처 없음 — 출처.txt 에 적기")]


try:
    FONT = find_font({})
except FontError:
    FONT = None


class FakeTTS:
    """무음 mp3 + 조각 시각 (조각마다 0.5초)."""

    def __init__(self, tmp: Path):
        self.tmp, self.texts, self.voices = tmp, [], []

    def synthesize_parts(self, parts, voice, rate=1.0):
        self.texts.append(" ".join(p.text for p in parts))
        self.voices.append(voice)
        mp3 = self.tmp / f"tts{len(self.texts)}.mp3"
        end = 0.5 * len(parts)
        ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(end), "-c:a", "libmp3lame", str(mp3)])
        return Speech(mp3.read_bytes(), [Word(p.text, 0.5 * i) for i, p in enumerate(parts)], end)


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_render_short_end_to_end(tmp_path):
    from pipelines.shopping_shorts.script import parse_cuts

    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (240, 200, 160)).save(buf, "PNG")
    fetched = []
    tts = FakeTTS(tmp_path)
    out = render_short(parse_cuts(BLOCKS), POST.disclosure, tts=tts,
                       fetch=lambda url: fetched.append(url) or buf.getvalue(),
                       work=tmp_path / "work", out=tmp_path / "short.mp4", font=FONT,
                       voices={"여": "F", "남": "M"}, default_voice="여", rate=1.0, lexicon={"얇은": "얄븐"})
    assert fetched == ["https://s3/1.png"]
    assert tts.texts[1] == "이럴 땐 쓰리엠 같은 얄븐 솔을 써 보세요. 틈에 대고 문질러요."
    assert tts.texts[-1] == "제품 정보는 프로필 링크에서 확인하세요."
    assert tts.voices == ["F", "M", "F"]
    # 컷 1·마무리: 14자 넘어 두 줄 = 2조각 (1.0초) + 0.4 · 컷 2: #4초 고정
    assert media_duration(out) == pytest.approx(1.4 + 4.0 + 1.4, abs=0.3)


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_seconds_tag_shorter_than_speech_is_error(tmp_path):
    with pytest.raises(ValueError, match="#1초"):
        render_short(parse_cuts_for([para("가 [쉼 0.1] 나 [쉼 0.1] 다 #1초")]), "문구", tts=FakeTTS(tmp_path),
                     fetch=lambda url: b"", work=tmp_path / "w", out=tmp_path / "o.mp4", font=FONT,
                     voices={"여": "F", "남": "M"}, default_voice="여", rate=1.0, lexicon={})


def parse_cuts_for(blocks):
    from pipelines.shopping_shorts.script import parse_cuts
    return parse_cuts(blocks)
