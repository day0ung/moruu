# moruu — AI 에이전트 작업 규칙 (Codex · Claude 공통)

쇼핑 콘텐츠(Threads·쿠팡·YouTube 쇼츠)와 시니어 롱폼 AI 드라마를 반자동으로 만드는 Python 프로젝트. 관리는 Notion, 실행은 로컬 또는 GitHub Actions(수동 실행).

계획: docs/PLAN.md · 구조 그림: README.md · 사람이 할 일: docs/TODO-manual.md · Notion 속성·본문 형식: docs/notion-schema.md
설계: docs/superpowers/specs/ · 구현 계획: docs/superpowers/plans/ · 조사: docs/research/

## 절대 규칙
- 키·토큰 값을 출력·커밋·로그하지 않는다. `.env`는 키 이름만 확인한다. `.env`·`.env.example` 의 값은 커밋하지 않는다.
- `status=APPROVED`는 사람만 바꾼다. 에이전트는 DRAFT(롱폼은 `기획`·DRAFT)까지만 만든다. `기획승인`도 사람이 바꾼다.
- 링크 글에는 대가성 문구가 링크 바로 옆에 있어야 한다.
- 써보지 않은 경험을 1인칭으로 쓰지 않는다. 숫자·가격은 확인된 것만. "최고·필수·무조건·혁신적" 금지.
- YouTube는 항상 비공개 업로드 → 사람이 공개.
- 게시 시간 랜덤 위장 등 탐지 회피 설계를 하지 않는다.
- 사람이 요청하지 않으면 커밋·push 하지 않는다. push·Notion 페이지 삭제처럼 되돌리기 어려운 일은 먼저 묻는다.

## 구조
- core/ 공통 (설정·로깅·Notion·안전 규칙), channels/ 플랫폼 클라이언트 (TTS·영상·Drive·텔레그램·AI 모델), pipelines/ 콘텐츠 흐름
- pipelines끼리 import 금지 — 같이 쓰는 코드는 channels/ 나 core/ 로
- Notion 속성 이름은 core/schema.py 와 docs/notion-schema.md 를 같이 고친다.

## 작업 방식
- 테스트 먼저 (pytest). 바깥 서비스(Notion·TTS·Drive·텔레그램·AI)는 가짜 객체·`httpx.MockTransport` 로. 테스트에 실제 키가 필요하면 안 된다.
- 주석·문서·커밋 메시지는 한국어로 짧게. 커밋 메시지 `feat: …` / `fix: …` / `docs: …`.
- 주변 코드의 스타일(짧은 함수, dataclass, 모듈 docstring 에 형식 설명)을 따른다. 새 외부 라이브러리는 꼭 필요할 때만.

## 명령
- 설치: `uv sync` (Windows 에서 `uv` 가 PATH 에 없으면 `.venv/Scripts/python.exe -m …`)
- 테스트: `uv run pytest`
- 게시/수집 시험: `uv run python -m pipelines.threads_post --dry-run`
- 쇼츠 렌더: `uv run python -m pipelines.shopping_shorts [--dry-run] [--content-id ID]` → `out/shorts/{content_id}.mp4` (대본 형식: docs/notion-schema.md)
- 드라마 렌더: `uv run python -m pipelines.ai_drama [--dry-run] [--content-id ID]` → `out/drama/{content_id}.mp4` + `.srt` + `.timeline.json` (대본·시리즈 바이블 형식: docs/notion-schema.md, TTS 캐시 `.cache/tts`)
- 클라우드 렌더: GitHub Actions `render` 수동 실행 (할 일 렌더/폴더, 대상, content_id). 쇼츠·드라마 `--from-drive` = Drive `moruu/{쇼츠|롱폼}/{content_id}/` 자료를 받아 렌더 → 같은 폴더에 결과 업로드 → 텔레그램 알림 (`--no-upload` 로 업로드 끔)
- 롱폼 AI 대본: `uv run python -m pipelines.ai_story plan --series 이름 [--topic 소재]` → 기획안 3개(status=기획) · `... write [--content-id ID]` → 기획승인 글 대본 → DRAFT. Actions `story` 수동 실행. AI 키: `GEMINI_API_KEY`/`OPENROUTER_API_KEY` (설계: docs/superpowers/specs/2026-10-30-ai-story-agent-design.md)
- 자료 폴더 만들기: `uv run python -m pipelines.media_folders` (Notion `자료 폴더` 채움) · Drive 토큰: `uv run python -m channels.gdrive.get_token [--check]` · 텔레그램: `uv run python -m channels.telegram [--chat-id | "시험"]` (준비: docs/TODO-manual.md 6-4)
- Threads 토큰 최초 발급/재발급: threads-auth-page 에서 코드 복사 → `uv run python -m channels.threads.get_token`

## 운영 메모
- 로컬에서 실제 게시(`--dry-run` 없이)는 GitHub Actions 예약 실행이 꺼져 있거나 겹치지 않을 때만 한다 (POSTING 점유는 원자적이지 않음).
- status=POSTING 으로 남은 글: Threads 앱에서 게시 여부 확인 → 게시됐으면 POSTED + 게시ID 입력, 안 됐으면 APPROVED 로 되돌림.
- FAILED + "network: 게시 여부 확인 필요": 위와 같이 확인 후 처리.
- 예약시각이 비어 있는 글은 게시되지 않는다.
