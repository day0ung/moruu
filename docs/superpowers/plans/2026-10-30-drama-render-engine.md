# 시니어 AI 드라마 렌더 엔진 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이 엔진은 Notion 에피소드 대본과 시리즈 바이블, 로컬 그림·음악 폴더를 받아 가로 1920×1080 `.mp4`·`.srt`·`timeline.json`을 만든다.

**Architecture:**
- 흐름은 대본 → `Timeline`(JSON) → 렌더다.
- 공통 부품은 `channels/`에 둔다: TTS 캐시, 타임라인, 렌더러, 화면 크기 인자.
- 드라마 고유 흐름은 `pipelines/ai_drama/`에 둔다: 바이블, 대본 파싱, 타임라인 만들기, CLI.
- 쇼츠 동작은 바꾸지 않는다.

**Tech Stack:** Python 3.12+, httpx, Pillow, imageio-ffmpeg(ffmpeg), pytest, Notion API 2022-06-28

**Spec:** `docs/superpowers/specs/2026-10-30-drama-render-engine-design.md`. 운영 쪽(Drive·Actions·텔레그램)은 `2026-10-30-cloud-render-ops-design.md`가 다루고, 이 계획의 범위 밖이다.

## Global Constraints

- **실행 경로:** 이 PC에는 `uv`가 PATH에 없다. 아래 경로로 실행한다.
  - 테스트: `.venv/Scripts/python.exe -m pytest -q` (bash) 또는 `.venv\Scripts\python.exe -m pytest -q` (PowerShell)
  - 계획 본문의 `PY`는 이 실행 파일을 뜻한다.
- **키·토큰:** 값을 출력·커밋·로그하지 않는다. `.env`는 키 이름만 본다. `.env.example`은 커밋하지 않는다.
- **import:** `pipelines`끼리 import하지 않는다. `pipelines/ai_drama`는 `pipelines/shopping_shorts`를 import하지 않는다.
- **Notion 속성 이름:** `core/schema.py`와 `docs/notion-schema.md`를 같이 고친다.
- **상태:** `status=APPROVED`는 사람만 바꾼다. 시험 렌더는 상태를 바꾸지 않는 스크립트로 한다.
- **쇼츠:** 기존 쇼츠 테스트(현재 135개 통과)는 모든 Task 뒤에도 통과해야 한다.
- **커밋:**
  - 메시지는 한국어 `feat: …` / `docs: …` 형식이다.
  - 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
- **스타일:** 주석과 docstring은 한국어로 짧게 쓴다. 기존 파일의 밀도를 따른다.
- **상수:**
  - 가로 화면 `(1920, 1080)`
  - 자막 줄 최대 `24`자
  - 줄 사이 `0.4`초, 장면 끝 여유 `1.0`초
  - 장면 전환 페이드 `0.3`초
  - 음악 `-18`dB, 곡 넘김 `2.0`초
  - 높낮이 `-20~20`, 빠르기 `0.25~4.0`
- **바이블 자막색:**
  - 흰색 `#FFFFFF`, 노랑 `#FFD400`, 하늘 `#7FD3FF`, 연두 `#A8E063`, 분홍 `#FF9EC4`, 주황 `#FFB347`, 보라 `#C3A6FF`
  - 자동 배정 순서: 노랑·하늘·연두·분홍·주황·보라 (내레이션은 흰색)

## 파일 구조

| 파일 | 책임 |
|---|---|
| `channels/tts/google.py` (수정) | `synthesize_parts(..., pitch=0.0)` |
| `channels/tts/cache.py` (새) | `CachedTTS`: 줄 단위 TTS 결과 저장·재사용 |
| `channels/tts/srt.py` (수정) | `cues_to_srt(cues)` 추가, `to_srt`가 이를 사용 |
| `channels/video/frames.py` (수정) | `subtitle_png`·`cover_png`에 `canvas`, `subtitle_png`에 `color` |
| `channels/video/ffmpeg.py` (수정) | `scene_args`(여러 음성·페이드·크기), `MusicSpan`, `mix_args`(음악 이어 깔기·줄이기) |
| `channels/video/timeline.py` (새) | `Clip`·`Subtitle`·`Scene`·`Timeline`, JSON, `.srt` |
| `channels/video/render.py` (새) | `render(timeline, work, out, font)`: 장면 조각 캐시 → concat → 음악 |
| `core/schema.py`, `core/models.py`, `core/notion_store.py` (수정) | `YT-롱폼`·`시리즈`·`영상 링크`, `Post.series`, `tables()`, `approved_drama()`, `mark_rendered(link)` |
| `core/config.py` (수정) | `DramaSettings` |
| `pipelines/ai_drama/bible.py` (새) | 표 → `Character` 사전 + 문제 |
| `pipelines/ai_drama/script.py` (새) | 블록 → `DramaScene` 목록, 그림·음악 붙이기, 검사 |
| `pipelines/ai_drama/build.py` (새) | 장면 + TTS → `Timeline` |
| `pipelines/ai_drama/__main__.py` (새) | CLI, 상태 변경, 업로드·알림 주입 자리 |
| `docs/notion-schema.md`, `CLAUDE.md`, `.gitignore` (수정) | 문서·명령·무시 목록 |

스펙과 다르게 구현하는 세부 두 가지:
- 연결된 시리즈 ID는 `series_of(post)` 대신 `Post.series`(relation 첫 ID)로 읽는다.
- `LINE_MAX` 같은 상수는 쇼츠처럼 모듈 상수로 `build.py`에 둔다. `DramaSettings`에는 환경변수 값만 둔다.

---

### Task 1: TTS 높낮이 + 줄 단위 캐시

**Files:**
- Modify: `channels/tts/google.py` (`synthesize_parts`)
- Create: `channels/tts/cache.py`
- Test: `tests/channels/test_tts.py`, `tests/channels/test_tts_cache.py`

**Interfaces:**
- Produces:
  - `GoogleTTS.synthesize_parts(parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech`
  - `CachedTTS(inner, folder: Path, provider: str = "google")`, 메서드 `.synthesize_parts`의 형태는 위와 같다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/channels/test_tts.py` 끝에 추가:
```python
def test_synthesize_parts_sends_pitch_only_when_set():
    sent = []

    def handler(req):
        sent.append(json.loads(req.content)["audioConfig"])
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"MP3").decode(), "timepoints": []})

    tts = make(handler)
    tts.synthesize_parts([Part("가")], "ko-KR-Neural2-A")
    tts.synthesize_parts([Part("가")], "ko-KR-Neural2-A", 0.9, -4.0)
    assert sent == [{"audioEncoding": "MP3", "speakingRate": 1.0},
                    {"audioEncoding": "MP3", "speakingRate": 0.9, "pitch": -4.0}]
```

`tests/channels/test_tts_cache.py` 새로 만들기:
```python
from channels.tts.cache import CachedTTS
from channels.tts.google import Part, Speech, Word


class Inner:
    def __init__(self):
        self.calls = []

    def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
        self.calls.append((tuple(parts), voice, rate, pitch))
        return Speech(f"MP3-{len(self.calls)}".encode(), [Word(p.text, 0.5 * i) for i, p in enumerate(parts)], 1.5)


def test_same_input_hits_cache(tmp_path):
    inner = Inner()
    tts = CachedTTS(inner, tmp_path)
    a = tts.synthesize_parts([Part("가", 0.5), Part("나")], "V", 0.9, -2.0)
    b = CachedTTS(inner, tmp_path).synthesize_parts([Part("가", 0.5), Part("나")], "V", 0.9, -2.0)
    assert len(inner.calls) == 1
    assert b == a == Speech(b"MP3-1", [Word("가", 0.0), Word("나", 0.5)], 1.5)


def test_any_change_misses_cache(tmp_path):
    inner = Inner()
    tts = CachedTTS(inner, tmp_path)
    base = ([Part("가", 0.5)], "V", 1.0, 0.0)
    tts.synthesize_parts(*base)
    tts.synthesize_parts([Part("가", 0.6)], "V", 1.0, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "W", 1.0, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "V", 1.1, 0.0)
    tts.synthesize_parts([Part("가", 0.5)], "V", 1.0, 1.0)
    CachedTTS(inner, tmp_path, provider="typecast").synthesize_parts(*base)
    assert len(inner.calls) == 6


def test_missing_end_roundtrips_as_none(tmp_path):
    class NoEnd(Inner):
        def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
            super().synthesize_parts(parts, voice, rate, pitch)
            return Speech(b"X", [], None)

    inner = NoEnd()
    CachedTTS(inner, tmp_path).synthesize_parts([Part("가")], "V")
    assert CachedTTS(inner, tmp_path).synthesize_parts([Part("가")], "V") == Speech(b"X", [], None)
    assert len(inner.calls) == 1
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/channels/test_tts.py tests/channels/test_tts_cache.py -q`
Expected: FAIL (`pitch` 인자 없음, `channels.tts.cache` 모듈 없음)

- [ ] **Step 3: 구현**

`channels/tts/google.py`의 `synthesize_parts`:
```python
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech:
        """조각마다 시각 (words[i] = parts[i]). 시각이 하나라도 빠지면 words 는 빈 목록. pitch: 반음."""
        if not any(p.text.strip() for p in parts):
            raise ValueError("빈 대본")
        audio = {"audioEncoding": "MP3", "speakingRate": rate}
        if pitch:
            audio["pitch"] = pitch
        body = {
            "input": {"ssml": build_ssml(parts)},
            "voice": {"languageCode": "-".join(voice.split("-")[:2]), "name": voice},
            "audioConfig": audio,
            "enableTimePointing": ["SSML_MARK"],
        }
```
(나머지 줄은 그대로.)

`channels/tts/cache.py`:
```python
"""TTS 결과를 줄 단위로 저장해 두고 같은 입력이면 다시 부르지 않는다 (.cache/tts/{sha256}.mp3 + .json)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from channels.tts.google import Part, Speech, Word


class PartsTTS(Protocol):
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech: ...


class CachedTTS:
    def __init__(self, inner: PartsTTS, folder: Path, provider: str = "google"):
        self.inner, self.folder, self.provider = inner, folder, provider

    def _key(self, parts: list[Part], voice: str, rate: float, pitch: float) -> str:
        raw = json.dumps([self.provider, voice, rate, pitch, [[p.text, p.pause_after] for p in parts]],
                         ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech:
        key = self._key(parts, voice, rate, pitch)
        mp3, meta = self.folder / f"{key}.mp3", self.folder / f"{key}.json"
        if mp3.is_file() and meta.is_file():
            data = json.loads(meta.read_text(encoding="utf-8"))
            return Speech(mp3.read_bytes(), [Word(t, s) for t, s in data["words"]], data["end"])
        speech = self.inner.synthesize_parts(parts, voice, rate, pitch)
        self.folder.mkdir(parents=True, exist_ok=True)
        mp3.write_bytes(speech.audio)
        # json 을 마지막에 쓴다 — 중간에 끊기면 캐시로 안 친다
        meta.write_text(json.dumps({"words": [[w.text, w.start] for w in speech.words], "end": speech.end},
                                   ensure_ascii=False), encoding="utf-8")
        return speech
```

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS. 쇼츠의 `FakeTTS.synthesize_parts(parts, voice, rate)` 호출은 pitch 없이도 그대로 동작해야 한다.

- [ ] **Step 5: 커밋**

```bash
git add channels/tts/google.py channels/tts/cache.py tests/channels/test_tts.py tests/channels/test_tts_cache.py
git commit -m "feat: TTS 높낮이와 줄 단위 캐시"
```

---

### Task 2: 가로 화면 자막·배경, 자막 색

**Files:**
- Modify: `channels/video/frames.py` (`_draw_lines`, `subtitle_png`, `cover_png`)
- Test: `tests/channels/test_video_frames.py`

**Interfaces:**
- Produces:
  - `subtitle_png(text, out, font_path, center_y=1420, size=64, color=WHITE, canvas=(W, H)) -> Path`
  - `cover_png(data, out, canvas=(W, H)) -> Path`
  - `hex_rgb("#FFD400") -> (255, 212, 0)`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/channels/test_video_frames.py` 끝에 추가. 이 파일의 기존 import와 `FONT` 정의를 확인해서 쓴다. 없으면 아래처럼 추가한다.
```python
import io

import pytest
from PIL import Image

from channels.video.frames import FontError, cover_png, find_font, hex_rgb, subtitle_png

try:
    FONT = find_font({})
except FontError:
    FONT = None


def test_hex_rgb():
    assert hex_rgb("#FFD400") == (255, 212, 0)
    assert hex_rgb("#7fd3ff") == (127, 211, 255)


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_subtitle_png_landscape_colored(tmp_path):
    out = subtitle_png("너희 이번 주말에 올 거니?", tmp_path / "s.png", FONT, center_y=960, size=56,
                       color=(255, 212, 0), canvas=(1920, 1080))
    with Image.open(out) as img:
        assert img.size == (1920, 1080)
        colors = {c for _, c in img.getcolors(1920 * 1080)}
    assert any(c[:3] == (255, 212, 0) and c[3] == 255 for c in colors)


def test_cover_png_landscape(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (800, 800), (10, 20, 30)).save(buf, "PNG")
    with Image.open(cover_png(buf.getvalue(), tmp_path / "c.png", canvas=(1920, 1080))) as img:
        assert img.size == (1920, 1080)
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/channels/test_video_frames.py -q`
Expected: FAIL (`hex_rgb` 없음, `canvas` 인자 없음)

- [ ] **Step 3: 구현**

`frames.py`:
```python
def hex_rgb(code: str) -> tuple[int, int, int]:
    code = code.lstrip("#")
    return int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16)
```
`_draw_lines`에 `width: int = W` 인자를 추가하고, 가운데 정렬 계산을 `x = (width - sum(...)) / 2`로 바꾼다. 기존 호출은 그대로 둔다.

```python
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


def cover_png(data: bytes, out: Path, canvas: tuple[int, int] = (W, H)) -> Path:
    """올린 이미지를 화면에 꽉 차게 가운데 잘라 저장."""
    with Image.open(io.BytesIO(data)) as src:
        img = ImageOps.fit(ImageOps.exif_transpose(src).convert("RGB"), canvas, Image.LANCZOS)
    img.save(out)
    return out
```
`_draw_lines`의 `fill=YELLOW if p.strong else fill`은 그대로 둔다. 자막은 strong이 없으므로 `color`가 그대로 쓰인다.

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add channels/video/frames.py tests/channels/test_video_frames.py
git commit -m "feat: 자막·배경 PNG 에 화면 크기와 자막 색"
```

---

### Task 3: ffmpeg 장면 인자와 음악 섞기 인자

**Files:**
- Modify: `channels/video/ffmpeg.py`
- Test: `tests/channels/test_video_ffmpeg.py`

**Interfaces:**
- Consumes: 기존 `Overlay`, `_ENCODE`, `FPS`, `ZOOM`, `run`
- Produces:
  - `scene_args(out: Path, background: Path, clips: list[tuple[Path, float]], duration: float, overlays: list[Overlay], size: tuple[int, int], fade: float = 0.3) -> list[str]`
  - `@dataclass(frozen=True) MusicSpan(path: Path, start: float, duration: float)`
  - `mix_args(video: Path, music: list[MusicSpan], out: Path, music_db: float = -18.0, xfade: float = 2.0) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/channels/test_video_ffmpeg.py`에 추가. import에 `MusicSpan, mix_args, scene_args`를 더한다.
```python
def test_scene_args_delays_each_clip_and_fades():
    args = scene_args(Path("s.mp4"), Path("bg.png"), [(Path("a.mp3"), 0.0), (Path("b.mp3"), 1.25)], 3.0,
                      [Overlay(Path("o.png"), 0.0, 1.0)], (1920, 1080), fade=0.3)
    graph = args[args.index("-filter_complex") + 1]
    assert args.count("-i") == 4  # 배경 + 음성 2 + 자막 1
    assert "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080" in graph
    assert "zoompan=" in graph and "s=1920x1080" in graph
    assert "[1:a]adelay=delays=0:all=1[c0]" in graph
    assert "[2:a]adelay=delays=1250:all=1[c1]" in graph
    assert "[c0][c1]amix=inputs=2:normalize=0,apad[a]" in graph
    assert "[v0][3:v]overlay=0:0:enable='between(t,0.000,1.000)'[v1]" in graph
    assert "fade=t=in:st=0:d=0.300,fade=t=out:st=2.700:d=0.300" in graph
    assert args[-1] == "s.mp4" and "-t" in args


def test_mix_args_crossfades_groups_and_ducks():
    args = mix_args(Path("v.mp4"), [MusicSpan(Path("calm.mp3"), 5.0, 30.0), MusicSpan(Path("sad.mp3"), 35.0, 20.0)],
                    Path("o.mp4"), music_db=-18, xfade=2.0)
    graph = args[args.index("-filter_complex") + 1]
    assert args[:5] == ["-y", "-i", "v.mp4", "-stream_loop", "-1"]
    assert "[1:a]atrim=0:32.000,asetpts=PTS-STARTPTS[m0]" in graph
    assert "[2:a]atrim=0:22.000,asetpts=PTS-STARTPTS[m1]" in graph
    assert "[m0][m1]acrossfade=d=2.000[x1]" in graph
    assert "[x1]adelay=delays=5000:all=1,volume=-18dB[mus]" in graph
    assert "sidechaincompress" in graph and "amix=inputs=2:normalize=0:duration=first[a]" in graph
    assert ["-map", "0:v", "-map", "[a]", "-c:v", "copy"] == args[args.index("-map"):args.index("-map") + 6]


def test_mix_args_single_group_no_crossfade():
    graph = mix_args(Path("v.mp4"), [MusicSpan(Path("calm.mp3"), 0.0, 10.0)], Path("o.mp4"))
    graph = graph[graph.index("-filter_complex") + 1]
    assert "acrossfade" not in graph and "[m0]adelay=delays=0:all=1,volume=-18dB[mus]" in graph


def test_real_scene_with_two_clips(tmp_path):
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1920, 1080), (200, 230, 220)).save(bg)
    a = silent_mp3(tmp_path / "a.mp3", 0.5)
    run(scene_args(tmp_path / "s.mp4", bg, [(a, 0.0), (a, 0.9)], 1.6, [], (1920, 1080)))
    assert media_duration(tmp_path / "s.mp4") == pytest.approx(1.6, abs=0.15)
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/channels/test_video_ffmpeg.py -q`
Expected: FAIL (ImportError)

- [ ] **Step 3: 구현**

`ffmpeg.py`에서 `segment_args`의 확대 문자열을 helper로 꺼낸다. 쇼츠 결과 문자열은 바뀌지 않아야 한다.
```python
def _fit(size: tuple[int, int], duration: float, zoom: bool) -> str:
    w, h = size
    base = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if zoom:
        frames = max(1, round(duration * FPS))
        # 2배로 키운 뒤 zoompan — 원본 크기에서 하면 떨림이 보인다
        base += (f",scale={w * 2}:{h * 2},zoompan=z='1+{ZOOM}*on/{frames}'"
                 f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={FPS}")
    return base
```
`segment_args`에서는 `base = _fit((W, H), duration, zoom)`을 쓴다.

```python
def scene_args(out: Path, background: Path, clips: list[tuple[Path, float]], duration: float,
               overlays: list[Overlay], size: tuple[int, int], fade: float = 0.3) -> list[str]:
    """드라마 장면 하나: 그림 확대 + 자막 + 줄 음성들을 시각에 맞춰 섞고, 앞뒤로 어두워졌다 밝아짐."""
    if not clips:
        raise ValueError("장면에 음성 없음")
    t = f"{duration:.3f}"
    args = ["-y", "-loop", "1", "-framerate", str(FPS), "-t", t, "-i", str(background)]
    for audio, _ in clips:
        args += ["-i", str(audio)]
    first = 1 + len(clips)
    for o in overlays:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", t, "-i", str(o.png)]

    chain = [f"[0:v]{_fit(size, duration, True)},setsar=1,format=yuv420p[v0]"]
    for i, o in enumerate(overlays):
        enable = "" if o.start is None else f":enable='between(t,{o.start:.3f},{o.stop:.3f})'"
        chain.append(f"[v{i}][{first + i}:v]overlay=0:0{enable}[v{i + 1}]")
    chain.append(f"[v{len(overlays)}]fade=t=in:st=0:d={fade:.3f},"
                 f"fade=t=out:st={duration - fade:.3f}:d={fade:.3f}[v]")
    for i, (_, start) in enumerate(clips):
        chain.append(f"[{i + 1}:a]adelay=delays={round(start * 1000)}:all=1[c{i}]")
    chain.append("".join(f"[c{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0,apad[a]")
    return args + ["-filter_complex", ";".join(chain), "-map", "[v]", "-map", "[a]", "-t", t, *_ENCODE, str(out)]


@dataclass(frozen=True)
class MusicSpan:
    path: Path
    start: float  # 영상 전체 기준 시작(초)
    duration: float


def mix_args(video: Path, music: list[MusicSpan], out: Path, music_db: float = -18.0,
             xfade: float = 2.0) -> list[str]:
    """음악 구간을 이어 깔고(곡 사이 xfade 초), 말할 때 줄인 뒤 영상 소리와 섞는다. 영상은 다시 인코딩하지 않음."""
    args = ["-y", "-i", str(video)]
    for m in music:
        args += ["-stream_loop", "-1", "-i", str(m.path)]
    chain = []
    for i, m in enumerate(music):
        # 다음 곡과 겹치는 만큼 늘려 둔다 — acrossfade 가 겹친 길이만큼 줄인다
        length = m.duration + (xfade if len(music) > 1 else 0)
        chain.append(f"[{i + 1}:a]atrim=0:{length:.3f},asetpts=PTS-STARTPTS[m{i}]")
    last = "m0"
    for i in range(1, len(music)):
        chain.append(f"[{last}][m{i}]acrossfade=d={xfade:.3f}[x{i}]")
        last = f"x{i}"
    chain.append(f"[{last}]adelay=delays={round(music[0].start * 1000)}:all=1,volume={music_db:g}dB[mus]")
    chain.append("[0:a]asplit=2[voice][sc]")
    chain.append("[mus][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck]")
    chain.append("[voice][duck]amix=inputs=2:normalize=0:duration=first[a]")
    return args + ["-filter_complex", ";".join(chain), "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(out)]
```
`acrossfade`에는 겹침 곡선 기본값을 쓴다.

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS. 기존 `test_segment_args_*`도 문자열이 같아서 통과해야 한다.

- [ ] **Step 5: 커밋**

```bash
git add channels/video/ffmpeg.py tests/channels/test_video_ffmpeg.py
git commit -m "feat: 드라마 장면·음악 섞기 ffmpeg 인자"
```

---

### Task 4: 타임라인 데이터와 자막 파일

**Files:**
- Create: `channels/video/timeline.py`
- Modify: `channels/tts/srt.py` (`cues_to_srt` 추가, `to_srt`가 사용)
- Test: `tests/channels/test_timeline.py`

**Interfaces:**
- Consumes: `channels.tts.srt.Cue(start, stop, text)`
- Produces:
  - `Clip(audio: Path, start: float)`
  - `Subtitle(text: str, color: str, start: float, stop: float)`: color는 `#RRGGBB`
  - `Scene(number: int, title: str, image: Path, music: Path | None, duration: float, clips: tuple[Clip, ...], subtitles: tuple[Subtitle, ...])`
  - `Timeline(width: int, height: int, scenes: tuple[Scene, ...])`
    - `.size -> tuple[int, int]`, `.starts() -> list[float]`, `.total -> float`
    - `.to_json() -> str`, `Timeline.from_json(text) -> Timeline`, `.to_srt() -> str`
  - `srt.cues_to_srt(cues: list[Cue]) -> str`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/channels/test_timeline.py`:
```python
from pathlib import Path

from channels.video.timeline import Clip, Scene, Subtitle, Timeline

TL = Timeline(1920, 1080, (
    Scene(1, "저녁 식탁", Path("img/01.png"), Path("music/잔잔.mp3"), 3.5,
          (Clip(Path("w/001_000.mp3"), 0.0), Clip(Path("w/001_001.mp3"), 1.9)),
          (Subtitle("그날 저녁,", "#FFFFFF", 0.0, 1.5), Subtitle("너희 올 거니?", "#FFD400", 1.9, 2.5))),
    Scene(2, "다음 날", Path("img/02.png"), None, 2.0,
          (Clip(Path("w/002_000.mp3"), 0.0),), (Subtitle("아침이 밝았다.", "#FFFFFF", 0.0, 1.0),)),
))


def test_starts_and_total():
    assert TL.starts() == [0.0, 3.5] and TL.total == 5.5 and TL.size == (1920, 1080)


def test_json_roundtrip():
    assert Timeline.from_json(TL.to_json()) == TL


def test_srt_uses_absolute_times():
    assert TL.to_srt() == (
        "1\n00:00:00,000 --> 00:00:01,500\n그날 저녁,\n\n"
        "2\n00:00:01,900 --> 00:00:02,500\n너희 올 거니?\n\n"
        "3\n00:00:03,500 --> 00:00:04,500\n아침이 밝았다.\n"
    )
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/channels/test_timeline.py -q`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`channels/tts/srt.py`:
```python
def cues_to_srt(cues: list[Cue]) -> str:
    return "\n".join(f"{n + 1}\n{_ts(c.start)} --> {_ts(c.stop)}\n{c.text}\n" for n, c in enumerate(cues))


def to_srt(words: list[Word], end: float | None, per: int = 3) -> str:
    return cues_to_srt(cues(words, end, per))
```

`channels/video/timeline.py`:
```python
"""렌더할 영상 한 편의 설계도 — 장면마다 그림·음악·줄 음성·자막과 시각. JSON 으로 저장해 검토·재사용한다.

장면 안의 시각(Clip.start, Subtitle.start/stop)은 장면 시작 기준. 전체 시각은 장면 길이를 차례로 더한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from channels.tts.srt import Cue, cues_to_srt


@dataclass(frozen=True)
class Clip:
    audio: Path
    start: float


@dataclass(frozen=True)
class Subtitle:
    text: str
    color: str  # #RRGGBB
    start: float
    stop: float


@dataclass(frozen=True)
class Scene:
    number: int
    title: str
    image: Path
    music: Path | None
    duration: float
    clips: tuple[Clip, ...]
    subtitles: tuple[Subtitle, ...]


@dataclass(frozen=True)
class Timeline:
    width: int
    height: int
    scenes: tuple[Scene, ...]

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def starts(self) -> list[float]:
        out, t = [], 0.0
        for s in self.scenes:
            out.append(t)
            t += s.duration
        return out

    @property
    def total(self) -> float:
        return sum(s.duration for s in self.scenes)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=1, default=lambda p: Path(p).as_posix())

    @classmethod
    def from_json(cls, text: str) -> Timeline:
        d = json.loads(text)
        return cls(d["width"], d["height"], tuple(
            Scene(s["number"], s["title"], Path(s["image"]), Path(s["music"]) if s["music"] else None,
                  s["duration"], tuple(Clip(Path(c["audio"]), c["start"]) for c in s["clips"]),
                  tuple(Subtitle(**x) for x in s["subtitles"]))
            for s in d["scenes"]))

    def to_srt(self) -> str:
        cues = [Cue(t + x.start, t + x.stop, x.text) for t, s in zip(self.starts(), self.scenes) for x in s.subtitles]
        return cues_to_srt(cues)
```

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS (기존 `to_srt` 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add channels/video/timeline.py channels/tts/srt.py tests/channels/test_timeline.py
git commit -m "feat: 렌더 타임라인 데이터와 srt"
```

---

### Task 5: 렌더러 (장면 조각 캐시 → 이어 붙이기 → 음악)

**Files:**
- Create: `channels/video/render.py`
- Test: `tests/channels/test_video_render.py`

**Interfaces:**
- Consumes:
  - `scene_args`, `MusicSpan`, `mix_args`, `concat`, `run`, `Overlay` (Task 3)
  - `subtitle_png`, `cover_png`, `hex_rgb` (Task 2)
  - `Timeline` (Task 4)
- Produces:
  - `render(timeline: Timeline, work: Path, out: Path, font: Path, *, music_db: float = -18.0, xfade: float = 2.0) -> Path`: `out`(.mp4)과 `out.with_suffix(".srt")`를 쓴다.
  - `music_spans(timeline) -> list[MusicSpan]`
  - `scene_key(scene, size) -> str`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/channels/test_video_render.py`:
```python
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from channels.video import render as R
from channels.video.ffmpeg import MusicSpan, media_duration, run
from channels.video.frames import FontError, find_font
from channels.video.timeline import Clip, Scene, Subtitle, Timeline

try:
    FONT = find_font({})
except FontError:
    FONT = None


def scene(n, music, duration=2.0, image=Path("i.png")):
    return Scene(n, f"장면{n}", image, music, duration, (Clip(Path("a.mp3"), 0.0),), ())


def test_music_spans_group_same_track_and_skip_leading_silence():
    a, b = Path("a.mp3"), Path("b.mp3")
    tl = Timeline(1920, 1080, (scene(1, None), scene(2, a), scene(3, a, 3.0), scene(4, b)))
    assert R.music_spans(tl) == [MusicSpan(a, 2.0, 5.0), MusicSpan(b, 7.0, 2.0)]
    assert R.music_spans(Timeline(1920, 1080, (scene(1, None),))) == []


def test_scene_key_changes_with_image_content(tmp_path):
    img, audio = tmp_path / "i.png", tmp_path / "a.mp3"
    img.write_bytes(b"one")
    audio.write_bytes(b"sound")
    s = Scene(1, "t", img, None, 2.0, (Clip(audio, 0.0),), (Subtitle("가", "#FFFFFF", 0, 1),))
    k1 = R.scene_key(s, (1920, 1080))
    assert R.scene_key(s, (1920, 1080)) == k1
    img.write_bytes(b"two")
    assert R.scene_key(s, (1920, 1080)) != k1
    assert R.scene_key(replace(s, duration=2.5), (1920, 1080)) != R.scene_key(s, (1920, 1080))


def silent(path, seconds):
    run(["-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds), "-c:a", "libmp3lame", str(path)])
    return path


def tone(path, seconds):
    run(["-y", "-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}", "-c:a", "libmp3lame", str(path)])
    return path


@pytest.mark.skipif(FONT is None, reason="한글 폰트 없음")
def test_render_two_scenes_with_music_and_reuses_segments(tmp_path):
    img = tmp_path / "01.png"
    Image.new("RGB", (640, 360), (120, 140, 160)).save(img)
    a = silent(tmp_path / "a.mp3", 0.6)
    music = tone(tmp_path / "m.mp3", 1.0)  # 장면보다 짧음 — 반복돼야 함
    subs = (Subtitle("그날 저녁,", "#FFD400", 0.0, 0.6),)
    tl = Timeline(1920, 1080, (
        Scene(1, "하나", img, music, 1.5, (Clip(a, 0.0), Clip(a, 0.7)), subs),
        Scene(2, "둘", img, music, 1.2, (Clip(a, 0.0),), ()),
    ))
    out = R.render(tl, tmp_path / "work", tmp_path / "ep.mp4", FONT)
    assert media_duration(out) == pytest.approx(2.7, abs=0.2)
    assert out.with_suffix(".srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000 --> 00:00:00,600\n그날 저녁,")

    made = sorted(p.name for p in (tmp_path / "work").glob("scene*.mp4"))
    stamp = [(tmp_path / "work" / n).stat().st_mtime_ns for n in made]
    R.render(tl, tmp_path / "work", tmp_path / "ep.mp4", FONT)
    assert [(tmp_path / "work" / n).stat().st_mtime_ns for n in made] == stamp  # 다시 안 만듦
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/channels/test_video_render.py -q`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`channels/video/render.py`:
```python
"""Timeline → mp4 + srt. 장면마다 조각을 만들고(내용이 같으면 재사용) 이어 붙인 뒤 음악을 깐다."""
from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from channels.video.ffmpeg import MusicSpan, Overlay, VideoError, concat, mix_args, run, scene_args
from channels.video.frames import cover_png, hex_rgb, subtitle_png
from channels.video.timeline import Scene, Timeline

FADE = 0.3  # 장면 앞뒤 어두워졌다 밝아짐(초)
SUB_SIZE = 56  # 가로 화면 자막 글자 크기
VERSION = "1"  # 장면 조각 모양을 바꾸면 올린다 — 캐시 무효화

log = logging.getLogger("moruu")


def scene_key(scene: Scene, size: tuple[int, int]) -> str:
    h = hashlib.sha256()
    h.update(f"{VERSION}|{size}|{scene.duration:.3f}|{FADE}|{SUB_SIZE}".encode())
    h.update(scene.image.read_bytes() if scene.image.is_file() else str(scene.image).encode())
    for c in scene.clips:
        h.update(f"|{c.start:.3f}|".encode())
        h.update(c.audio.read_bytes() if c.audio.is_file() else str(c.audio).encode())
    for s in scene.subtitles:
        h.update(f"|{s.text}|{s.color}|{s.start:.3f}|{s.stop:.3f}".encode())
    return h.hexdigest()


def music_spans(timeline: Timeline) -> list[MusicSpan]:
    spans: list[MusicSpan] = []
    for start, s in zip(timeline.starts(), timeline.scenes):
        if s.music is None:
            continue
        if spans and spans[-1].path == s.music and abs(spans[-1].start + spans[-1].duration - start) < 1e-6:
            last = spans.pop()
            spans.append(MusicSpan(last.path, last.start, last.duration + s.duration))
        else:
            spans.append(MusicSpan(s.music, start, s.duration))
    return spans


def _scene(s: Scene, size: tuple[int, int], work: Path, font: Path) -> Path:
    stem = f"scene{s.number:03}"
    seg = work / f"{stem}_{scene_key(s, size)[:16]}.mp4"
    if seg.is_file():
        return seg
    bg = cover_png(s.image.read_bytes(), work / f"{stem}_bg.png", canvas=size)
    overlays = [
        Overlay(subtitle_png(x.text, work / f"{stem}_sub{i}.png", font, center_y=size[1] - 120, size=SUB_SIZE,
                             color=hex_rgb(x.color), canvas=size), x.start, x.stop)
        for i, x in enumerate(s.subtitles)
    ]
    tmp = seg.with_name(seg.stem + "_tmp.mp4")
    try:
        run(scene_args(tmp, bg, [(c.audio, c.start) for c in s.clips], s.duration, overlays, size, FADE))
    except VideoError as e:
        raise VideoError(f"장면 {s.number}: {e}") from e
    tmp.replace(seg)  # 다 만들어진 뒤에만 캐시로 친다
    return seg


def render(timeline: Timeline, work: Path, out: Path, font: Path, *,
           music_db: float = -18.0, xfade: float = 2.0) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    segments = []
    for s in timeline.scenes:
        segments.append(_scene(s, timeline.size, work, font))
        log.info("장면 %d 완료", s.number)
    joined = concat(segments, work / "joined.mp4")
    spans = music_spans(timeline)
    if spans:
        run(mix_args(joined, spans, out, music_db, xfade))
    else:
        shutil.copyfile(joined, out)
    out.with_suffix(".srt").write_text(timeline.to_srt(), encoding="utf-8")
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS. 실제 렌더 테스트는 수 초 걸린다.

- [ ] **Step 5: 커밋**

```bash
git add channels/video/render.py tests/channels/test_video_render.py
git commit -m "feat: 타임라인 렌더러 — 장면 조각 캐시, 음악 줄이기"
```

---

### Task 6: Notion 스키마·저장소·설정

**Files:**
- Modify: `core/schema.py`, `core/models.py`, `core/notion_store.py`, `core/config.py`, `docs/notion-schema.md`
- Test: `tests/core/test_notion_store.py`, `tests/core/test_models.py`, `tests/core/test_config.py`

**Interfaces:**
- Produces:
  - `S.CH_YT_LONG = "YT-롱폼"`, `S.SERIES = "시리즈"`, `S.VIDEO_LINK = "영상 링크"`, `S.url(v) -> {"url": v}`
  - `Post.series: str = ""`: relation의 첫 페이지 ID
  - `NotionStore.tables(page_id) -> list[Table]`, `Table(rows: list[list[str]], header: bool)`
  - `NotionStore.approved_drama() -> list[Post]`
  - `NotionStore.mark_rendered(post, link: str | None = None)`
  - `DramaSettings.from_env(env, need_tts=True)`: 필드는 `notion_token, notion_db_content, notion_db_metrics, notion_db_failures, tts_key, tts_rate, lexicon_page`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/core/test_notion_store.py`에 추가:
```python
def test_approved_drama_filters_long_channel():
    store, sent = make_store([{"results": [page("p1", "YT-롱폼-1")], "has_more": False}])
    assert [p.content_id for p in store.approved_drama()] == ["YT-롱폼-1"]
    assert {"property": "채널", "select": {"equals": "YT-롱폼"}} in sent[0][2]["filter"]["and"]


def test_tables_reads_all_rows_with_header_flag():
    def row(*cells):
        return {"type": "table_row", "table_row": {"cells": [[{"plain_text": c}] for c in cells]}}

    store, sent = make_store([
        {"results": [{"type": "table", "id": "t1", "table": {"has_column_header": True}}], "has_more": False},
        {"results": [row("인물", "목소리"), row(" 아들 ", "ko-KR-Neural2-C")], "has_more": False},
    ])
    [t] = store.tables("series-1")
    assert t.header and t.rows == [["인물", "목소리"], ["아들", "ko-KR-Neural2-C"]]


def test_mark_rendered_with_link():
    store, sent = make_store([{}])
    store.mark_rendered(post(), "https://drive/x")
    assert sent[0][2]["properties"]["영상 링크"] == {"url": "https://drive/x"}
```
기존 `test_mark_rendered_sets_status_and_clears_error`에는 `assert "영상 링크" not in props`를 추가한다.

`tests/core/test_models.py`에 추가. 이 파일의 페이지 helper 형태를 확인하고, 아래처럼 `properties`에 relation을 넣는다.
```python
def test_series_relation_first_id():
    page = {"id": "p", "properties": {"content_id": {"title": [{"plain_text": "YT-롱폼-1"}]},
                                      "시리즈": {"relation": [{"id": "series-1"}, {"id": "series-2"}]}}}
    assert parse_post(page).series == "series-1"
    assert parse_post({"id": "p", "properties": {}}).series == ""
```

`tests/core/test_config.py`에 추가:
```python
from core.config import DramaSettings


def test_drama_settings_from_env():
    env = {"NOTION_TOKEN": "t", "NOTION_DB_CONTENT": "c", "NOTION_DB_METRICS": "m", "NOTION_DB_FAILURES": "f",
           "GOOGLE_TTS_API_KEY": "k", "TTS_RATE": "1.1", "NOTION_PAGE_LEXICON": "lex"}
    s = DramaSettings.from_env(env)
    assert (s.tts_key, s.tts_rate, s.lexicon_page) == ("k", 1.1, "lex")
    assert DramaSettings.from_env({k: v for k, v in env.items() if k != "GOOGLE_TTS_API_KEY"}, need_tts=False).tts_key == ""
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/core -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`core/schema.py`:
- `RENDERED` 위에 `CH_YT_LONG = "YT-롱폼"`을 둔다.
- `VOICE` 아래에 `SERIES = "시리즈"  # 롱폼: 시리즈 DB 연결`과 `VIDEO_LINK = "영상 링크"  # 렌더 결과 주소`를 둔다.
- `checkbox` 아래에 추가:
```python
def url(value: str) -> dict:
    return {"url": value}
```

`core/models.py`:
- `Post`에 `series: str = ""`를 추가한다.
- `parse_post`에 `series=next((r["id"] for r in get(S.SERIES).get("relation") or []), "")`를 추가한다.

`core/notion_store.py`:
```python
@dataclass(frozen=True)
class Table:
    rows: list[list[str]]  # 칸 글자 (앞뒤 공백 제거), 머리글 행 포함
    header: bool  # 첫 행이 머리글
```
- `approved_shorts`는 `_approved(channel)` helper를 거치도록 바꾼다.
```python
    def _approved(self, channel: str) -> list[Post]:
        filter_ = {"and": [
            {"property": S.STATUS, "select": {"equals": S.APPROVED}},
            {"property": S.CHANNEL, "select": {"equals": channel}},
        ]}
        pages = self._query(self._dbs.content, filter_, [{"timestamp": "created_time", "direction": "ascending"}])
        return [parse_post(p) for p in pages]

    def approved_shorts(self) -> list[Post]:
        return self._approved(S.CH_YT_SHOP)

    def approved_drama(self) -> list[Post]:
        return self._approved(S.CH_YT_LONG)

    def tables(self, page_id: str) -> list[Table]:
        """페이지의 표 블록들 → 칸 글자."""
        def cell(c: list[dict]) -> str:
            return "".join(r.get("plain_text", "") for r in c).strip()

        return [
            Table([[cell(c) for c in row.get("table_row", {}).get("cells", [])] for row in self.page_blocks(t["id"])],
                  bool(t["table"].get("has_column_header")))
            for t in self.page_blocks(page_id) if t.get("type") == "table"
        ]

    def lexicon(self, page_id: str) -> dict[str, str]:
        """발음 사전 페이지의 표 → {글자: 읽기}. 머리글 행과 빈 칸은 건너뛴다."""
        out: dict[str, str] = {}
        for t in self.tables(page_id):
            for cells in t.rows[1:] if t.header else t.rows:
                if len(cells) >= 2 and cells[0] and cells[1]:
                    out[cells[0]] = cells[1]
        return out

    def mark_rendered(self, post: Post, link: str | None = None) -> None:
        props = {S.STATUS: S.select(S.RENDERED), S.ERROR: {"rich_text": []}}
        if link:
            props[S.VIDEO_LINK] = S.url(link)
        self._update(post.page_id, props)
```

`core/config.py`의 `ShortsSettings` 아래:
```python
@dataclass(frozen=True)
class DramaSettings:
    """드라마 렌더용 — 목소리는 시리즈 바이블에서, 여기엔 Notion + TTS 키만."""
    notion_token: str
    notion_db_content: str
    notion_db_metrics: str
    notion_db_failures: str
    tts_key: str
    tts_rate: float = 1.0  # 바이블 빠르기가 비었을 때
    lexicon_page: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str], need_tts: bool = True) -> DramaSettings:
        required = SHORTS_REQUIRED + (("GOOGLE_TTS_API_KEY",) if need_tts else ())
        missing = [k for k in required if not env.get(k)]
        if missing:
            raise ConfigError("환경변수 없음: " + ", ".join(missing))
        return cls(
            notion_token=env["NOTION_TOKEN"],
            notion_db_content=env["NOTION_DB_CONTENT"],
            notion_db_metrics=env["NOTION_DB_METRICS"],
            notion_db_failures=env["NOTION_DB_FAILURES"],
            tts_key=env.get("GOOGLE_TTS_API_KEY", ""),
            tts_rate=float(env.get("TTS_RATE") or 1.0),
            lexicon_page=env.get("NOTION_PAGE_LEXICON", ""),
        )
```

`docs/notion-schema.md`:
- 콘텐츠 DB 속성 표에 `시리즈`(relation → 시리즈 DB, 롱폼만)와 `영상 링크`(url, 렌더가 채움)를 추가한다.
- 새 절 "시리즈 DB (롱폼)"를 추가한다: 바이블 표 칸, 기본값, 자막색 이름 목록.
- 새 절 "롱폼(드라마) 본문 형식"을 추가한다: 스펙 1절의 본문 예시와 규칙, 미디어 폴더.

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS (기존 lexicon 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add core/ docs/notion-schema.md tests/core/
git commit -m "feat: 롱폼 채널·시리즈 연결·영상 링크, Notion 표 읽기, DramaSettings"
```

---

### Task 7: 시리즈 바이블

**Files:**
- Create: `pipelines/ai_drama/__init__.py` (빈 파일), `pipelines/ai_drama/bible.py`
- Test: `tests/pipelines/test_drama_bible.py`

**Interfaces:**
- Consumes: 표 행 목록 `list[list[list[str]]]` (Task 6 `Table.rows`, 첫 행 = 머리글)
- Produces:
  - `NARRATOR = "내레이션"`
  - `Character(name: str, voice: str, pitch: float, rate: float, color: str)`
  - `parse_bible(tables: list[list[list[str]]], default_rate: float) -> tuple[dict[str, Character], list[str]]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/pipelines/test_drama_bible.py`:
```python
from pipelines.ai_drama.bible import Character, parse_bible

HEAD = ["인물", "나이·성격", "목소리", "높낮이", "빠르기", "자막색"]


def test_columns_by_header_defaults_and_auto_colors():
    cast, problems = parse_bible([[HEAD,
                                   ["내레이션", "", "ko-KR-Neural2-A", "", "0.95", ""],
                                   ["시어머니", "68세", "ko-KR-Neural2-A", "-4", "", ""],
                                   ["아들", "", "ko-KR-Neural2-C", "", "", "#7fd3ff"],
                                   ["며느리", "", "ko-KR-Neural2-B", "2", "1.1", "분홍"],
                                   ["", "", "", "", "", ""]]], default_rate=1.0)
    assert problems == []
    assert cast == {
        "내레이션": Character("내레이션", "ko-KR-Neural2-A", 0.0, 0.95, "#FFFFFF"),
        "시어머니": Character("시어머니", "ko-KR-Neural2-A", -4.0, 1.0, "#FFD400"),
        "아들": Character("아들", "ko-KR-Neural2-C", 0.0, 1.0, "#7FD3FF"),
        "며느리": Character("며느리", "ko-KR-Neural2-B", 2.0, 1.1, "#FF9EC4"),
    }


def test_auto_colors_skip_used_ones():
    cast, _ = parse_bible([[["인물", "목소리", "자막색"], ["내레이션", "V", ""], ["갑", "V", "노랑"], ["을", "V", ""]]], 1.0)
    assert cast["을"].color == "#7FD3FF"


def test_problems():
    cast, problems = parse_bible([[["인물", "목소리", "높낮이", "빠르기", "자막색"],
                                   ["아들", "", "30", "abc", "검정"]]], 1.0)
    assert problems == [
        "바이블: 아들 목소리 없음",
        "바이블: 아들 높낮이 -20~20 아님 (30)",
        "바이블: 아들 빠르기 0.25~4.0 아님 (abc)",
        "바이블: 아들 자막색 모름 (검정) — 흰색·노랑·하늘·연두·분홍·주황·보라 또는 #RRGGBB",
        "바이블: 내레이션 줄 없음",
    ]


def test_no_table():
    assert parse_bible([[["글자", "읽기"]]], 1.0) == ({}, ["바이블 표 없음 — 머리글에 인물·목소리 칸"])
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/pipelines/test_drama_bible.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`pipelines/ai_drama/bible.py`:
```python
"""시리즈 바이블 표 → 인물별 목소리·높낮이·빠르기·자막색.

머리글로 칸을 찾는다 (순서 무관): 인물 | 목소리 | 높낮이 | 빠르기 | 자막색. 다른 칸(나이·성격, 그림 설명)은 무시.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NARRATOR = "내레이션"
COLORS = {"흰색": "#FFFFFF", "노랑": "#FFD400", "하늘": "#7FD3FF", "연두": "#A8E063",
          "분홍": "#FF9EC4", "주황": "#FFB347", "보라": "#C3A6FF"}
AUTO = ["노랑", "하늘", "연두", "분홍", "주황", "보라"]
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


@dataclass(frozen=True)
class Character:
    name: str
    voice: str
    pitch: float  # 반음
    rate: float
    color: str  # #RRGGBB


def _number(text: str, low: float, high: float) -> float | None:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if low <= value <= high else None


def parse_bible(tables: list[list[list[str]]], default_rate: float) -> tuple[dict[str, Character], list[str]]:
    table = next((t for t in tables if t and "인물" in t[0] and "목소리" in t[0]), None)
    if table is None:
        return {}, ["바이블 표 없음 — 머리글에 인물·목소리 칸"]
    head = table[0]

    def col(row: list[str], name: str) -> str:
        return row[head.index(name)].strip() if name in head and head.index(name) < len(row) else ""

    problems: list[str] = []
    rows = []
    for row in table[1:]:
        name = col(row, "인물")
        if not name:
            continue
        voice = col(row, "목소리")
        if not voice:
            problems.append(f"바이블: {name} 목소리 없음")
        pitch_raw, rate_raw, color_raw = col(row, "높낮이"), col(row, "빠르기"), col(row, "자막색")
        pitch = _number(pitch_raw, -20, 20) if pitch_raw else 0.0
        if pitch is None:
            problems.append(f"바이블: {name} 높낮이 -20~20 아님 ({pitch_raw})")
        rate = _number(rate_raw, 0.25, 4.0) if rate_raw else default_rate
        if rate is None:
            problems.append(f"바이블: {name} 빠르기 0.25~4.0 아님 ({rate_raw})")
        if color_raw in COLORS:
            color = COLORS[color_raw]
        elif _HEX.fullmatch(color_raw):
            color = color_raw.upper()
        elif not color_raw:
            color = COLORS["흰색"] if name == NARRATOR else ""
        else:
            problems.append(f"바이블: {name} 자막색 모름 ({color_raw}) — "
                            f"{'·'.join(COLORS)} 또는 #RRGGBB")
            color = COLORS["흰색"]
        rows.append([name, voice, pitch or 0.0, rate or default_rate, color])

    used = {r[4] for r in rows}
    free = iter([COLORS[c] for c in AUTO if COLORS[c] not in used] + [COLORS[c] for c in AUTO] * 10)
    for r in rows:
        if not r[4]:
            r[4] = next(free)
    if not any(r[0] == NARRATOR for r in rows):
        problems.append(f"바이블: {NARRATOR} 줄 없음")
    return {r[0]: Character(*r) for r in rows}, problems
```

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest tests/pipelines/test_drama_bible.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add pipelines/ai_drama/__init__.py pipelines/ai_drama/bible.py tests/pipelines/test_drama_bible.py
git commit -m "feat: 드라마 시리즈 바이블 표 읽기"
```

---

### Task 8: 에피소드 대본 파싱과 렌더 전 검사

**Files:**
- Create: `pipelines/ai_drama/script.py`
- Test: `tests/pipelines/test_drama_script.py`

**Interfaces:**
- Consumes: `NARRATOR` (Task 7), `channels.tts.narration.problems`, `core.safety.banned_words`
- Produces:
  - `Spoken(speaker: str, emotion: str, raw: str)`: 내레이션이면 `speaker == NARRATOR`
  - `DramaScene(number: int, title: str, music: str | None, lines: list[Spoken], image: Path | None = None, image_source: str = "")`. `music`은 이어 가기를 적용한 실제 태그다.
  - `parse_episode(blocks: list[dict], names: set[str]) -> tuple[list[DramaScene], list[str]]`
  - `attach_images(scenes, folder: Path) -> list[str]`
  - `find_music(tags: set[str], folder: Path) -> tuple[dict[str, Path], list[str]]`
  - `script_problems(scenes) -> list[str]`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/pipelines/test_drama_script.py`:
```python
from pathlib import Path

from pipelines.ai_drama.script import (DramaScene, Spoken, attach_images, find_music, parse_episode,
                                       script_problems)


def rt(text):
    return [{"plain_text": text, "annotations": {}}]


def h2(text):
    return {"type": "heading_2", "heading_2": {"rich_text": rt(text)}}


def para(text):
    return {"type": "paragraph", "paragraph": {"rich_text": rt(text)}}


NAMES = {"내레이션", "시어머니", "아들"}
BLOCKS = [
    {"type": "callout", "callout": {"rich_text": rt("메모")}},
    h2("장면 1 · 저녁 식탁 #음악 잔잔"),
    para("그날 저녁, 시어머니는 말없이 상을 차렸다.\n시어머니(서운하게): 너희 이번 주말에 올 거니?\n\n아들: 회사 일이 좀… [쉼 0.5]"),
    h2("장면 2 · 다음 날"),
    para("시간이 흘러: 봄이 왔다."),
    h2("장면 3 #음악 슬픔"),
    para("끝."),
]


def test_parse_scenes_speakers_and_music_carry():
    scenes, problems = parse_episode(BLOCKS, NAMES)
    assert problems == []
    assert scenes[0] == DramaScene(1, "장면 1 · 저녁 식탁", "잔잔", [
        Spoken("내레이션", "", "그날 저녁, 시어머니는 말없이 상을 차렸다."),
        Spoken("시어머니", "서운하게", "너희 이번 주말에 올 거니?"),
        Spoken("아들", "", "회사 일이 좀… [쉼 0.5]"),
    ])
    assert (scenes[1].title, scenes[1].music, scenes[1].lines) == (
        "장면 2 · 다음 날", "잔잔", [Spoken("내레이션", "", "시간이 흘러: 봄이 왔다.")])
    assert (scenes[2].title, scenes[2].music) == ("장면 3", "슬픔")


def test_unknown_name_and_lines_before_scene():
    scenes, problems = parse_episode([para("앞줄"), h2("장면"), para("며느리: 어머니"), para("결론: 끝")], NAMES)
    assert problems == ["장면 제목 전에 대사 — 첫 줄은 ## 장면 제목", "장면 1: 인물 '며느리' 바이블에 없음",
                        "장면 1: 인물 '결론' 바이블에 없음"]


def test_attach_images_by_number_with_sources(tmp_path):
    for name in ("01.png", "3.jpg", "09.png", "메모.txt", "ep.mp4"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("AI:Gemini\n03: https://pexels.com/1\n", encoding="utf-8")
    scenes = [DramaScene(n, "t", None, []) for n in (1, 2, 3)]
    assert attach_images(scenes, tmp_path) == ["09.png: 9번 장면 없음"]
    assert (scenes[0].image.name, scenes[0].image_source) == ("01.png", "AI:Gemini")
    assert scenes[1].image is None
    assert (scenes[2].image.name, scenes[2].image_source) == ("3.jpg", "https://pexels.com/1")
    assert attach_images(scenes, tmp_path / "없음") == []


def test_find_music(tmp_path):
    (tmp_path / "잔잔.mp3").write_bytes(b"x")
    (tmp_path / "슬픔.m4a").write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("잔잔: YouTube 오디오 보관함\n", encoding="utf-8")
    music, problems = find_music({"잔잔", "슬픔", "긴장"}, tmp_path)
    assert music == {"잔잔": tmp_path / "잔잔.mp3", "슬픔": tmp_path / "슬픔.m4a"}
    assert problems == ["음악 '긴장' 파일 없음 — 긴장.mp3", "음악 '슬픔' 출처 없음 — 출처.txt 에 적기"]


def test_script_problems(tmp_path):
    ok = DramaScene(1, "a", None, [Spoken("내레이션", "", "좋은 하루")], tmp_path / "01.png", "AI")
    assert script_problems([ok]) == []
    bad = [
        DramaScene(1, "a", None, []),
        DramaScene(2, "b", None, [Spoken("아들", "", "최고 {3M 쓰리엠}")], tmp_path / "02.png", ""),
    ]
    assert script_problems(bad) == [
        "장면 1: 대사 없음",
        "장면 1: 그림 없음 — 01.png",
        "장면 2: 02.png 출처 없음 — 출처.txt 에 적기",
        "장면 2: 읽는 법 {글자|읽기} 형식 오류",
        "장면 2: 금지어 최고",
    ]
    assert script_problems([]) == ["장면 없음 — 본문에 ## 장면 제목과 대사"]
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/pipelines/test_drama_script.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`pipelines/ai_drama/script.py`:
```python
"""Notion 에피소드 본문 블록 → 장면 목록 + 검사.

형식 (docs/notion-schema.md):
  ## 장면 제목 #음악 잔잔         ← 제목2 = 새 장면. 음악 태그 없으면 앞 장면 곡을 이어 감
  그날 저녁, …                    ← 문단 한 줄 = 대사 한 줄. 이름이 없으면 내레이션
  시어머니(서운하게): 너희 …       ← 바이블 인물 이름: 대사 (괄호 = 감정, 지금은 기록만)
그 밖의 블록(콜아웃·인용·코드·제목1·3)은 메모로 무시한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from channels.tts import narration
from core.safety import banned_words
from pipelines.ai_drama.bible import NARRATOR

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MUSIC_EXT = (".mp3", ".m4a", ".wav")
SOURCES_FILE = "출처.txt"
_MUSIC_TAG = re.compile(r"\s*#음악\s+(\S+)")
_SPEAKER = re.compile(r"^([^\s:()]{1,8})(?:\(([^)]*)\))?:\s*(.+)$")
_SOURCE_LINE = re.compile(r"^\s*([^:\s]+)\s*:\s*(.+)$")


@dataclass(frozen=True)
class Spoken:
    speaker: str  # 바이블 인물 이름 또는 내레이션
    emotion: str
    raw: str  # {…}·[쉼] 그대로


@dataclass
class DramaScene:
    number: int
    title: str
    music: str | None  # 이어 가기 적용된 음악 태그
    lines: list[Spoken] = field(default_factory=list)
    image: Path | None = None
    image_source: str = ""


def _plain(block: dict) -> str:
    body = block.get(block.get("type")) or {}
    return "".join(r.get("plain_text", "") for r in body.get("rich_text", []))


def parse_episode(blocks: list[dict], names: set[str]) -> tuple[list[DramaScene], list[str]]:
    scenes: list[DramaScene] = []
    problems: list[str] = []
    early = False
    for b in blocks:
        kind = b.get("type")
        if kind == "heading_2":
            text = _plain(b)
            m = _MUSIC_TAG.search(text)
            music = m[1] if m else (scenes[-1].music if scenes else None)
            scenes.append(DramaScene(len(scenes) + 1, _MUSIC_TAG.sub("", text).strip(), music))
        elif kind == "paragraph":
            for line in (x.strip() for x in _plain(b).split("\n")):
                if not line:
                    continue
                if not scenes:
                    early = True
                    continue
                m = _SPEAKER.match(line)
                if m and m[1] in names and m[1] != NARRATOR:
                    scenes[-1].lines.append(Spoken(m[1], m[2] or "", m[3].strip()))
                elif m and m[1] not in names:
                    problems.append(f"장면 {scenes[-1].number}: 인물 '{m[1]}' 바이블에 없음")
                else:
                    scenes[-1].lines.append(Spoken(NARRATOR, "", line))
    if early:
        problems.insert(0, "장면 제목 전에 대사 — 첫 줄은 ## 장면 제목")
    return scenes, problems


def _sources(folder: Path, is_key: Callable[[str], bool]) -> tuple[dict[str, str], str]:
    """출처.txt → ({키: 출처}, 기본 출처). '키: 출처' 줄은 is_key(키) 일 때만 — "AI:Gemini" 같은 줄은 기본 출처."""
    path = folder / SOURCES_FILE
    by_key, default = {}, ""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _SOURCE_LINE.match(line)
            if m and is_key(m[1]):
                by_key[m[1].lstrip("0") if m[1].isdigit() else m[1]] = m[2].strip()
            elif line.strip():
                default = line.strip()
    return by_key, default


def attach_images(scenes: list[DramaScene], folder: Path) -> list[str]:
    """folder 의 01.png, 2.jpg … 를 같은 번호 장면 그림으로."""
    if not folder.is_dir():
        return []
    by_key, default = _sources(folder, str.isdigit)
    out = []
    for f in sorted(folder.iterdir()):
        if not f.stem.isdigit() or f.suffix.lower() not in IMAGE_EXT:
            continue
        n = int(f.stem)
        if n > len(scenes) or n < 1:
            out.append(f"{f.name}: {n}번 장면 없음")
            continue
        scenes[n - 1].image = f
        scenes[n - 1].image_source = by_key.get(str(n), default)
    return out


def find_music(tags: set[str], folder: Path) -> tuple[dict[str, Path], list[str]]:
    """음악 태그 → folder/{태그}.mp3 (.m4a/.wav). 출처는 folder/출처.txt 의 '태그: 출처' 또는 기본 줄."""
    by_key, default = _sources(folder, tags.__contains__)
    found, problems = {}, []
    for tag in sorted(tags):
        path = next((folder / f"{tag}{ext}" for ext in MUSIC_EXT if (folder / f"{tag}{ext}").is_file()), None)
        if path is None:
            problems.append(f"음악 '{tag}' 파일 없음 — {tag}.mp3")
            continue
        found[tag] = path
        if not (by_key.get(tag) or default):
            problems.append(f"음악 '{tag}' 출처 없음 — {SOURCES_FILE} 에 적기")
    return found, problems


def script_problems(scenes: list[DramaScene]) -> list[str]:
    if not scenes:
        return ["장면 없음 — 본문에 ## 장면 제목과 대사"]
    out = []
    for s in scenes:
        tag = f"장면 {s.number}"
        if not s.lines:
            out.append(f"{tag}: 대사 없음")
        if s.image is None:
            out.append(f"{tag}: 그림 없음 — {s.number:02}.png")
        elif not s.image_source:
            out.append(f"{tag}: {s.image.name} 출처 없음 — {SOURCES_FILE} 에 적기")
        out += [f"{tag}: {p}" for x in s.lines for p in narration.problems(x.raw)]
        for w in banned_words(" ".join(x.raw for x in s.lines) + " " + s.title):
            out.append(f"{tag}: 금지어 {w}")
    return out
```
참고:
- `from collections.abc import Callable`을 import에 추가한다.
- 그림은 숫자 키만 받는다. `03: url`은 키 `"3"`이 된다. 음악은 실제로 쓰인 태그만 키로 받는다.
- 그래서 `AI:Gemini`나 `https://…` 같은 줄은 기본 출처가 된다.
- 테스트 기대 순서: 음악 문제는 태그 이름순(`sorted`)으로 나온다. "긴장"이 "슬픔"보다 앞이다.

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest tests/pipelines/test_drama_script.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add pipelines/ai_drama/script.py tests/pipelines/test_drama_script.py
git commit -m "feat: 드라마 에피소드 대본 파싱과 렌더 전 검사"
```

---

### Task 9: 타임라인 만들기 (TTS → 시각)

**Files:**
- Create: `pipelines/ai_drama/build.py`
- Test: `tests/pipelines/test_drama_build.py`

**Interfaces:**
- Consumes:
  - `DramaScene`, `Spoken` (Task 8), `Character` (Task 7)
  - `narration.to_lines`, `srt.line_cues`, `media_duration`
  - `Timeline`, `Scene`, `Clip`, `Subtitle` (Task 4)
- Produces:
  - `SIZE = (1920, 1080)`, `LINE_MAX = 24`, `GAP = 0.4`, `SCENE_TAIL = 1.0`
  - `build_timeline(scenes: list[DramaScene], cast: Mapping[str, Character], tts, lexicon: Mapping[str, str], work: Path, music: Mapping[str, Path]) -> Timeline`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/pipelines/test_drama_build.py`:
```python
from pathlib import Path

import pytest

from channels.tts.google import Speech, Word
from channels.video.timeline import Clip, Subtitle
from pipelines.ai_drama.bible import Character
from pipelines.ai_drama.build import build_timeline
from pipelines.ai_drama.script import DramaScene, Spoken

CAST = {"내레이션": Character("내레이션", "N", 0.0, 1.0, "#FFFFFF"),
        "시어머니": Character("시어머니", "M", -4.0, 0.9, "#FFD400")}


class FakeTTS:
    """조각마다 0.5초, 끝 = 조각 수 × 0.5."""

    def __init__(self):
        self.calls = []

    def synthesize_parts(self, parts, voice, rate=1.0, pitch=0.0):
        self.calls.append((" ".join(p.text for p in parts), voice, rate, pitch))
        return Speech(b"MP3", [Word(p.text, 0.5 * i) for i, p in enumerate(parts)], 0.5 * len(parts))


def test_times_colors_voices(tmp_path):
    scenes = [
        DramaScene(1, "저녁", "잔잔", [Spoken("내레이션", "", "그날 저녁, 시어머니는 말없이 상을 차렸다."),
                                      Spoken("시어머니", "서운하게", "너희 올 거니?")], tmp_path / "01.png", "AI"),
        DramaScene(2, "아침", None, [Spoken("내레이션", "", "{3M|쓰리엠} 아침")], tmp_path / "02.png", "AI"),
    ]
    tts = FakeTTS()
    tl = build_timeline(scenes, CAST, tts, {}, tmp_path / "w", {"잔잔": tmp_path / "잔잔.mp3"})

    assert tts.calls == [("그날 저녁, 시어머니는 말없이 상을 차렸다.", "N", 1.0, 0.0),
                         ("너희 올 거니?", "M", 0.9, -4.0),
                         ("쓰리엠 아침", "N", 1.0, 0.0)]
    s1, s2 = tl.scenes
    # 내레이션 24자 초과 → 자막 두 줄(조각 2개, 1.0초), 다음 줄은 1.0 + 0.4 에 시작
    assert s1.clips == (Clip(tmp_path / "w" / "001_000.mp3", 0.0), Clip(tmp_path / "w" / "001_001.mp3", 1.4))
    assert [x.color for x in s1.subtitles] == ["#FFFFFF", "#FFFFFF", "#FFD400"]
    assert s1.subtitles[-1] == Subtitle("너희 올 거니?", "#FFD400", 1.4, 1.9)
    assert s1.duration == pytest.approx(1.9 + 1.0)
    assert (s1.music, s2.music) == (tmp_path / "잔잔.mp3", None)
    assert s2.subtitles == (Subtitle("3M 아침", "#FFFFFF", 0.0, 0.5),)
    assert (tl.width, tl.height) == (1920, 1080)
    assert (tmp_path / "w" / "002_000.mp3").read_bytes() == b"MP3"
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/pipelines/test_drama_build.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`pipelines/ai_drama/build.py`:
```python
"""장면 목록 + 바이블 + TTS → Timeline. 줄마다 TTS 를 부르고 자막 시각을 정한다."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from channels.tts import narration
from channels.tts.google import Part, Speech
from channels.tts.srt import line_cues
from channels.video.ffmpeg import media_duration
from channels.video.timeline import Clip, Scene, Subtitle, Timeline
from pipelines.ai_drama.bible import Character
from pipelines.ai_drama.script import DramaScene

SIZE = (1920, 1080)
LINE_MAX = 24  # 가로 화면 자막 한 줄 글자 수
GAP = 0.4  # 줄 사이 쉼(초)
SCENE_TAIL = 1.0  # 장면 마지막 줄 뒤 여유(초)


class TTS(Protocol):
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech: ...


def build_timeline(scenes: list[DramaScene], cast: Mapping[str, Character], tts: TTS,
                   lexicon: Mapping[str, str], work: Path, music: Mapping[str, Path]) -> Timeline:
    work.mkdir(parents=True, exist_ok=True)
    out = []
    for s in scenes:
        t, clips, subs = 0.0, [], []
        for i, sp in enumerate(s.lines):
            who = cast[sp.speaker]
            lines = narration.to_lines(sp.raw, lexicon, LINE_MAX)
            speech = tts.synthesize_parts([p for x in lines for p in x.parts], who.voice, who.rate, who.pitch)
            audio = work / f"{s.number:03}_{i:03}.mp3"
            audio.write_bytes(speech.audio)
            spoken = speech.end if speech.end is not None else media_duration(audio)
            clips.append(Clip(audio, t))
            subs += [Subtitle(c.text, who.color, t + c.start, t + c.stop) for c in line_cues(lines, speech.words, spoken)]
            t += spoken + GAP
        duration = max(t - GAP, 0.0) + SCENE_TAIL
        out.append(Scene(s.number, s.title, s.image, music.get(s.music) if s.music else None,
                         duration, tuple(clips), tuple(subs)))
    return Timeline(*SIZE, tuple(out))
```
조각 2개짜리 내레이션 기대값을 확인한다. "그날 저녁, 시어머니는 말없이 상을 차렸다."는 24자를 넘는다(공백 포함 25자). 그래서 쉼표 뒤에서 나뉘어 조각이 2개가 되고, 길이는 1.0이다. 이 조건이 맞지 않으면 테스트 문장을 더 길게 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest tests/pipelines/test_drama_build.py -q`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add pipelines/ai_drama/build.py tests/pipelines/test_drama_build.py
git commit -m "feat: 드라마 타임라인 만들기"
```

---

### Task 10: CLI와 상태 흐름

**Files:**
- Create: `pipelines/ai_drama/__main__.py`
- Modify: `.gitignore` (`.cache/`, `assets/music/`), `CLAUDE.md` (명령 한 줄)
- Test: `tests/pipelines/test_drama_pipeline.py`

**Interfaces:**
- Consumes: Task 6–9 전부, `channels.video.render.render`, `CachedTTS`, `GoogleTTS`
- Produces:
  - `run(store, build, render, log, *, dry_run=False, content_id=None, assets=ASSETS, music_dir=MUSIC, default_rate=1.0, uploader=None, notifier=None) -> int`
    - `store`: `approved_drama()`, `page_blocks(id)`, `tables(id) -> list[Table]`, `mark_failed(post, err)`, `mark_rendered(post, link=None)`
    - `build(post, scenes, cast, music) -> Timeline`: dry-run에서는 `None`을 줄 수 있다. 그러면 TTS 없이 파싱만 한다.
    - `render(post, timeline) -> Path`
    - `uploader(post, path) -> str` | None
    - `notifier(text) -> None` | None

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/pipelines/test_drama_pipeline.py`:
```python
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
    ep = tmp_path / "assets" / POST.content_id
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
    store = Store([replace(POST, series="")])
    assert run(store, lambda *a: pytest.fail("X"), lambda *a: pytest.fail("X"), LOG, **media) == 1
    assert store.failed == [("YT-롱폼-1", "시리즈 연결 없음; 장면 1: 인물 '아들' 바이블에 없음")]


def test_errors_prefixed_and_continue(media):
    other = replace(POST, page_id="p2", content_id="YT-롱폼-2")
    (media["assets"] / "YT-롱폼-2").mkdir()
    for name in ("01.png", "출처.txt"):
        (media["assets"] / "YT-롱폼-2" / name).write_bytes((media["assets"] / POST.content_id / name).read_bytes())

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
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `PY -m pytest tests/pipelines/test_drama_pipeline.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`pipelines/ai_drama/__main__.py`:
```python
"""python -m pipelines.ai_drama [--dry-run] [--content-id ID]

Notion 콘텐츠 DB 의 채널=YT-롱폼, status=APPROVED 페이지 → out/drama/{content_id}.mp4 · .srt · .timeline.json
→ status=RENDERED. 인물·목소리는 연결된 시리즈 페이지의 바이블 표, 그림은 assets/longform/{content_id}/01.png …,
음악은 assets/music/{태그}.mp3. --dry-run: 검사 + (TTS 키가 있으면) 장면별 길이만, 상태는 안 바꾼다.
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
RENDER_ERRORS = (VideoError, FontError, OSError, ValueError)


def _clock(sec: float) -> str:
    m, s = divmod(round(sec), 60)
    return f"{m}분 {s:02}초"


def run(store, build: Callable | None, render: Callable[[Post, Timeline], Path], log: logging.Logger, *,
        dry_run: bool = False, content_id: str | None = None, assets: Path = ASSETS, music_dir: Path = MUSIC,
        default_rate: float = 1.0, uploader: Callable[[Post, Path], str] | None = None,
        notifier: Callable[[str], None] | None = None) -> int:
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
                for start, s in zip(tl.starts(), tl.scenes):
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
        except (TTSError, httpx.HTTPError, *RENDER_ERRORS) as e:
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
        (OUT / f"{post.content_id}.timeline.json").write_text(tl.to_json(), encoding="utf-8")
        return tl

    def render(post: Post, timeline: Timeline) -> Path:
        return render_timeline(timeline, OUT / post.content_id, OUT / f"{post.content_id}.mp4", font)

    return run(store, build if tts else None, render, log, dry_run=args.dry_run, content_id=args.content_id,
               default_rate=s.tts_rate)


if __name__ == "__main__":
    sys.exit(main())
```
`test_problems_mark_failed`의 기대값이 맞는지 확인한다. 시리즈가 없으면 cast가 비어서 `아들:` 줄이 "바이블에 없음"이 된다. `내레이션`이 cast에 없어도 내레이션 줄은 `Spoken(NARRATOR)`로 들어가는데, 렌더 전에 막히므로 문제없다.

`.gitignore`에 `.cache/`와 `assets/music/`를 추가한다.

`CLAUDE.md`의 명령 목록 쇼츠 렌더 아래에 추가:
```
- 드라마 렌더: `uv run python -m pipelines.ai_drama [--dry-run] [--content-id ID]` → `out/drama/{content_id}.mp4` (+ .srt, .timeline.json) (대본·바이블 형식: docs/notion-schema.md)
```

- [ ] **Step 4: 통과 확인**

Run: `PY -m pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add pipelines/ai_drama/__main__.py tests/pipelines/test_drama_pipeline.py .gitignore CLAUDE.md
git commit -m "feat: 드라마 렌더 CLI 와 상태 흐름"
```

---

### Task 11: Notion 세팅과 실제 렌더 확인

**Files:**
- Notion(MCP): 시리즈 DB, 콘텐츠 DB 속성, 시험 시리즈·에피소드, 🎬 롱폼 작업실 페이지
- Scratch: `{scratchpad}/drama/test_render.py` (커밋하지 않음)

- [ ] **Step 1: Notion 콘텐츠 DB 속성 추가**

`mcp__notion__notion-update-data-source`로 콘텐츠 DB(data source `collection://e0d9d00b-080d-4139-8a9f-5ce09d5935a2`)에 속성 두 개를 추가한다.
- `영상 링크`: url
- `시리즈`: relation → 새 시리즈 DB. Step 2 다음에 추가한다.

- [ ] **Step 2: 시리즈 DB 만들기**

허브 페이지 `4060676ed1e9814198dbdd7c8cb96bbd` 아래에 `📚 시리즈` DB를 만든다.
- 속성: 이름(title), 채널(select: YT-롱폼), 메모(text)
- 시험 페이지 `시험 시리즈`를 만든다. 본문은 스펙의 바이블 표 형식으로 쓰고, 머리글 행을 켠다.
  - 행: 내레이션 / 시어머니 / 아들
- 콘텐츠 DB에 `시리즈` relation을 추가한다.

- [ ] **Step 3: 시험 에피소드 DRAFT 만들기**

콘텐츠 DB에 `YT-롱폼-시험-001`을 만든다: 채널 YT-롱폼, status DRAFT, 시리즈 = 시험 시리즈.
- 본문은 장면 3개다. 각 장면에 내레이션과 인물 대사를 2~3줄씩 넣고, 장면 1·3에 음악 태그를 단다.
- 금지어는 쓰지 않는다. 지어낸 숫자나 가격도 쓰지 않는다.

- [ ] **Step 4: 로컬 자료 준비 (scratch)**

- `assets/longform/YT-롱폼-시험-001/01~03.png`: Pillow로 색 다른 단색 그림을 만든다.
- `출처.txt`에 `시험용 단색 이미지`를 적는다.
- `assets/music/잔잔.mp3`, `assets/music/슬픔.mp3`: ffmpeg `sine`으로 20초 톤을 만든다.
- 음악 `출처.txt`에는 `시험용 합성 톤`을 적는다.
- 이 자료들은 모두 gitignore 대상이다.

- [ ] **Step 5: dry-run 확인**

DRAFT라서 `run()`이 고르지 않는다. 그래서 scratch 스크립트로 확인한다. 스크립트는 `NotionStore`로 해당 페이지를 직접 `parse_post`하고, `run`에 가짜 store를 넘긴다. 이 store는 `approved_drama()`가 그 Post 하나를 돌려주고, `mark_*`는 로그만 남긴다.
- 먼저 `dry_run=True`로 돌려 장면별 길이를 확인한다.

- [ ] **Step 6: 실제 렌더**

같은 스크립트를 `dry_run=False`로 돌린다. 상태는 바꾸지 않는다.
- 결과: `out/drama/YT-롱폼-시험-001.mp4`, `.srt`, `.timeline.json`

- [ ] **Step 7: 화면 확인**

1. `ffmpeg -ss {t} -frames:v 1`로 장면마다 1장씩 프레임을 뽑아 Read로 본다. 확인할 것:
   - 1920×1080인지
   - 자막이 한 줄인지
   - 인물마다 색이 다른지
   - 장면 경계에서 어두워지는지
2. 같은 스크립트를 한 번 더 돌린다.
   - TTS 호출 0회: 캐시 파일 수가 그대로여야 한다.
   - `scene*.mp4`를 다시 만들지 않는지 확인한다.

- [ ] **Step 8: 작업실 페이지와 문서 정리**

- 🎬 롱폼 작업실 페이지 `4090676ed1e981a7a70ee9f8d8a9c435`의 옛 컷 단위 안내를 드라마 형식으로 바꾼다.
  - 바이블 표 링크, 본문 예시, 폴더 규칙, 렌더 명령을 넣는다.
- `docs/notion-schema.md`가 실제 Notion과 맞는지 다시 확인한다.
- 커밋:
```bash
git add docs/notion-schema.md
git commit -m "docs: 롱폼 드라마 Notion 형식 정리"
```

- [ ] **Step 9: 사람에게 확인 요청**

`out/drama/YT-롱폼-시험-001.mp4` 경로를 알려 주고, 음악 줄이기와 전환을 직접 들어 봐 달라고 요청한다.
