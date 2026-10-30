import io

import pytest
from PIL import Image

from channels.video.frames import (
    H, W, YELLOW, FontError, Span, caption_png, card_png, cover_png, find_font, subtitle_png,
)

try:
    FONT = find_font({})
except FontError:
    FONT = None
needs_font = pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")


def colors(path):
    return {c for _, c in Image.open(path).convert("RGBA").getcolors(W * H)}


def test_find_font_env_override(tmp_path):
    f = tmp_path / "x.ttf"
    assert find_font({"MORUU_FONT": str(f)}) == f


@needs_font
def test_caption_is_transparent_frame_with_yellow_emphasis(tmp_path):
    out = caption_png([Span("가스레인지 모서리 "), Span("기름때", True)], tmp_path / "c.png", FONT)
    img = Image.open(out)
    assert img.size == (W, H) and img.mode == "RGBA"
    assert img.getpixel((5, H - 5))[3] == 0  # 글자 밖은 투명
    assert (*YELLOW, 255) in colors(out)


@needs_font
def test_long_caption_wraps_inside_frame(tmp_path):
    out = caption_png([Span("아주 긴 문장을 여러 줄로 나눠서 화면 밖으로 나가지 않게")], tmp_path / "c.png", FONT, tilt=0)
    alpha = Image.open(out).getchannel("A")
    left, _, right, _ = alpha.getbbox()
    assert left > 0 and right < W


@needs_font
def test_one_line_caption_shrinks_to_fit(tmp_path):
    out = caption_png([Span("가스레인지 모서리 "), Span("기름때", True)], tmp_path / "c.png", FONT, tilt=0, one_line=True)
    left, top, right, bottom = Image.open(out).getchannel("A").getbbox()
    assert left > 0 and right < W
    assert bottom - top < 130  # 한 줄 (100px 글자 두 줄이면 230px 이상)


@needs_font
def test_one_line_caption_too_long_wraps_at_min_size(tmp_path):
    out = caption_png([Span("가나다 " * 12)], tmp_path / "c.png", FONT, tilt=0, one_line=True)
    left, _, right, _ = Image.open(out).getchannel("A").getbbox()
    assert left > 0 and right < W


@needs_font
def test_subtitle_has_no_yellow(tmp_path):
    out = subtitle_png("솔 끝을 틈에", tmp_path / "s.png", FONT)
    assert (*YELLOW, 255) not in colors(out)


@needs_font
def test_card_with_notes(tmp_path):
    out = card_png(tmp_path / "card.png", FONT, notes=["제품 모양·크기는 상품 페이지에서 확인"])
    img = Image.open(out)
    assert img.size == (W, H) and len(colors(out)) > 1


def test_cover_crops_landscape_to_portrait(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (1600, 900), (10, 200, 10)).save(buf, "JPEG")
    out = cover_png(buf.getvalue(), tmp_path / "bg.png")
    assert Image.open(out).size == (W, H)


def test_words_keep_emphasis_inside_one_word():
    from channels.video.frames import _words
    words = _words([Span("제품 정보는 "), Span("프로필 링크", True), Span("에서")])
    assert ["".join(p.text for p in w).strip() for w in words] == ["제품", "정보는", "프로필", "링크에서"]
    assert [p.strong for p in words[-1]] == [True, False]
