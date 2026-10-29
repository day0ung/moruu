# 쇼핑 쇼츠 1차 — Notion 장면 대본 → 로컬 mp4

2026-10-29 · 브레인스토밍 결과. 기획: 50~60대 주부 생활꿀템 쇼츠, 시안 이미지(자막 스타일 참고).

## 범위

| 1차 (이 문서) | 2차 이후 |
|---|---|
| Notion 본문 파싱·검사 → 장면별 TTS → 카드·자막 PNG → ffmpeg 합성 → `out/shorts/{content_id}.mp4` → status=RENDERED | YouTube 비공개 업로드(`channels/youtube`), 이미지 생성 API(`channels/imagegen`), AI 영상, Actions 예약 실행 |

## 원칙 (CLAUDE.md·기존 결정)

- 화면은 **일러스트**(사람이 ChatGPT/Gemini로 생성해 Notion에 올림) + 글자 카드. 실사풍 AI 제품 사용 장면·전/후 비교 금지.
- 금지어(최고·필수·무조건·혁신적), 써보지 않은 1인칭 금지. 금지어는 코드로 검사.
- 이미지마다 캡션에 출처(`AI:ChatGPT`, 무료 사이트 URL 등). 없으면 렌더하지 않음.
- 마무리 카드는 자동: "제품 정보는 프로필 링크에서" + "모양·크기는 상품 페이지에서 확인" + 페이지의 `대가성문구`.

## Notion 본문 형식

```
## 장면 1 · 이미지          ← heading_2, "장면 N · 카드|이미지|AI영상"
```코드 블록 = 이미지 프롬프트```   ← 무시
[이미지 블록, 캡션 = 출처]       ← 이미지 장면 필수
화면: 가스레인지 모서리 **기름때**  ← 굵게 = 노란 강조
내레이션: 가스레인지 모서리, 닦기 불편하셨죠?
```
- 그 밖의 블록(콜아웃, 구분선, 회색 안내 문단)은 무시. 첫 `## 장면` 이전 블록도 무시.
- `AI영상` 은 "1차 미지원" 오류.

## 검사 (하나라도 걸리면 status=FAILED, 오류 칸에 사유)

장면 0개 · 장면 종류 오류 · 내레이션 없음 · 이미지 장면에 이미지 없음 / 캡션(출처) 없음 · 화면 문구 30자 초과 · 금지어 · `대가성문구` 비어 있음.

## 렌더

- 1080×1920, 30fps, H.264 + AAC. 장면마다 세그먼트 mp4 → concat.
- 장면 길이 = TTS 끝 시각 + 0.4초. 마무리 카드도 TTS("제품 정보는 프로필 링크에서 확인하세요.").
- 이미지 장면: 화면을 꽉 채우게 잘라서(cover) 천천히 확대(zoompan, 1.0→1.08).
- 카드 장면·마무리: 크림색 배경.
- 화면 문구: 상단, 굵은 한글 폰트, 흰 글씨 + 검은 외곽선, 굵게 = 노랑, -3° 기울임.
- 내레이션 자막: 하단 1/4 위쪽, 3단어씩, TTS 단어 시각에 맞춰 표시.
- 텍스트는 Pillow로 투명 PNG를 그려 ffmpeg overlay(`enable=between(t,a,b)`)로 겹침 — libass 의존 없음.
- 폰트: `MORUU_FONT` → `assets/fonts/*.ttf|otf` → 맑은 고딕 Bold / Apple SD 고딕 Neo / Noto Sans CJK.

## 코드 배치

| 위치 | 내용 |
|---|---|
| `core/schema.py` | `CH_YT_SHOP`, `RENDERED` |
| `core/safety.py` | `banned_words(text)` |
| `core/notion_store.py` | `approved_shorts()`, `page_blocks(page_id)`, `mark_rendered(post)` |
| `core/config.py` | `ShortsSettings` (Notion + TTS 키만) |
| `channels/tts/srt.py` | `cues()` 분리 (`to_srt` 가 사용) |
| `channels/video/` | `text.py` (Pillow), `ffmpeg.py` (세그먼트·concat) |
| `pipelines/shopping_shorts/` | `script.py` (블록 → 장면·검사), `render.py` (조립), `__main__.py` (CLI) |

CLI: `uv run python -m pipelines.shopping_shorts [--dry-run] [--content-id ID]` — dry-run 은 파싱·검사 결과만 출력, Notion·TTS 호출은 읽기만.

## 오류 처리

- 검사 실패 → FAILED + 사유 (사람이 고쳐서 다시 APPROVED).
- TTS·다운로드·ffmpeg 오류 → FAILED + "render: …". 한 페이지 실패가 다른 페이지를 막지 않음.

## 테스트

- 파서: Notion 블록 JSON 픽스처 → 장면·문제 목록.
- 텍스트 PNG: 크기·투명도·강조 색 픽셀 존재.
- ffmpeg: 인자 조립 단위 테스트 + 실제 ffmpeg 로 짧은 저해상도 렌더 1회.
- 파이프라인: 가짜 Notion/TTS 로 성공·실패 상태 전이.
