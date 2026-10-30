"""쇼츠 화면 한 장씩 — Pillow 로 배경·글자 PNG 를 그린다 (ffmpeg 가 겹쳐서 영상으로 만듦).

글자는 화면 전체 크기의 투명 PNG 로 그려서 overlay=0:0 으로 겹친다.
"""
from __future__ import annotations

import io
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1920
CREAM = (255, 246, 229)
WHITE = (255, 255, 255)
YELLOW = (255, 212, 0)
BLACK = (0, 0, 0)
INK = (60, 50, 40)

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_FONTS = (
    "C:/Windows/Fonts/malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
)


class FontError(Exception):
    pass


@dataclass(frozen=True)
class Span:
    text: str
    strong: bool = False  # True = 노란 강조


def find_font(env: Mapping[str, str] = os.environ) -> Path:
    """MORUU_FONT → assets/fonts/ → 시스템 한글 굵은 폰트."""
    if env.get("MORUU_FONT"):
        return Path(env["MORUU_FONT"])
    local = sorted(p for p in (ROOT / "assets" / "fonts").glob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
    for p in [*local, *map(Path, SYSTEM_FONTS)]:
        if p.exists():
            return p
    raise FontError("한글 폰트 없음 — MORUU_FONT 에 .ttf 경로를 넣거나 assets/fonts/ 에 폰트를 둘 것")


def hex_rgb(code: str) -> tuple[int, int, int]:
    code = code.lstrip("#")
    return int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)


def _words(spans: list[Span]) -> list[list[Span]]:
    """띄어쓰기 단위 단어. "프로필 **링크**에서" 처럼 강조가 단어 중간에 끝나도 한 단어로 묶는다."""
    words: list[list[Span]] = [[]]
    for s in spans:
        for piece in re.findall(r"\S+\s*|\s+", s.text):
            if piece.strip():
                words[-1].append(Span(piece, s.strong))
            elif words[-1]:
                words[-1][-1] = Span(words[-1][-1].text + piece, words[-1][-1].strong)
            if piece[-1].isspace() and words[-1]:
                words.append([])
    return [w for w in words if w]


def _wrap(spans: list[Span], font: ImageFont.FreeTypeFont, max_w: int) -> list[list[Span]]:
    """단어 단위로 줄바꿈. 강조 여부는 조각마다 유지."""
    lines: list[list[Span]] = [[]]
    for word in _words(spans):
        text = "".join(x.text for x in [*lines[-1], *word]).rstrip()
        if lines[-1] and font.getlength(text) > max_w:
            lines.append([])
        lines[-1].extend(word)
    return [line for line in lines if line]


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[list[Span]], font: ImageFont.FreeTypeFont,
                center_y: int, stroke: int, fill=WHITE, line_gap: float = 1.25, width: int = W) -> None:
    size = font.size
    top = center_y - (len(lines) * size * line_gap) / 2
    for i, line in enumerate(lines):
        line[-1] = Span(line[-1].text.rstrip(), line[-1].strong)
        x = (width - sum(font.getlength(p.text) for p in line)) / 2
        y = top + i * size * line_gap
        for p in line:
            draw.text((x, y), p.text, font=font, fill=YELLOW if p.strong else fill,
                      stroke_width=stroke, stroke_fill=BLACK)
            x += font.getlength(p.text)


def caption_png(spans: list[Span], out: Path, font_path: Path, center_y: int = 300,
                size: int = 100, tilt: float = 3.0, one_line: bool = False, min_size: int = 60) -> Path:
    """큰 화면 문구 — 흰 글씨 + 검은 외곽선, 강조는 노랑, 살짝 기울임.

    one_line: 한 줄에 들어가게 글자를 min_size 까지 줄인다. 그래도 넘치면 min_size 로 줄바꿈.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    max_w = W - 140
    font = ImageFont.truetype(str(font_path), size)
    if one_line:
        text = "".join(x.text for x in spans).strip()
        while size > min_size and font.getlength(text) > max_w:
            size -= 4
            font = ImageFont.truetype(str(font_path), max(size, min_size))
    _draw_lines(ImageDraw.Draw(img), _wrap(spans, font, max_w), font, center_y, stroke=max(6, font.size // 10))
    if tilt:
        img = img.rotate(tilt, resample=Image.BICUBIC, center=(W / 2, center_y))
    img.save(out)
    return out


def subtitle_png(text: str, out: Path, font_path: Path, center_y: int = 1420, size: int = 64,
                 color: tuple[int, int, int] = WHITE, canvas: tuple[int, int] = (W, H)) -> Path:
    """대사 자막 — 하단, 색 글씨 + 검은 외곽선. canvas: 화면 크기 (기본 세로 쇼츠)."""
    cw, ch = canvas
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    font = ImageFont.truetype(str(font_path), size)
    _draw_lines(ImageDraw.Draw(img), _wrap([Span(text)], font, cw - 160), font, center_y, stroke=6,
                fill=color, width=cw)
    img.save(out)
    return out


def card_png(out: Path, font_path: Path | None = None, notes: list[str] = ()) -> Path:
    """카드 배경 (크림색). notes 는 아래쪽에 작은 글씨로 (마무리 카드의 안내·대가성 문구)."""
    img = Image.new("RGB", (W, H), CREAM)
    if notes:
        font = ImageFont.truetype(str(font_path), 40)
        draw = ImageDraw.Draw(img)
        lines = [line for n in notes for line in _wrap([Span(n)], font, W - 160)]
        _draw_lines(draw, lines, font, center_y=1200, stroke=0, fill=INK, line_gap=1.5)
    img.save(out)
    return out


def cover_png(data: bytes, out: Path, canvas: tuple[int, int] = (W, H)) -> Path:
    """올린 이미지를 화면에 꽉 차게 가운데 잘라 저장."""
    with Image.open(io.BytesIO(data)) as src:
        img = ImageOps.fit(ImageOps.exif_transpose(src).convert("RGB"), canvas, Image.LANCZOS)
    img.save(out)
    return out
