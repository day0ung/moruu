# moruu — Claude 작업 규칙

계획: docs/PLAN.md · 구조 그림: README.md · 근거 자료: ../gomgom/정리/

## 절대 규칙
- 키·토큰 값을 출력·커밋·로그하지 않는다. `.env`는 키 이름만 확인한다.
- `status=APPROVED`는 사람만 바꾼다. Claude는 DRAFT까지만 만든다.
- 링크 글에는 대가성 문구가 링크 바로 옆에 있어야 한다.
- 써보지 않은 경험을 1인칭으로 쓰지 않는다. 숫자·가격은 확인된 것만. "최고·필수·무조건·혁신적" 금지.
- YouTube는 항상 비공개 업로드 → 사람이 공개.
- 게시 시간 랜덤 위장 등 탐지 회피 설계를 하지 않는다.

## 구조
- core/ 공통 (설정·로깅·Notion·안전 규칙), channels/ 플랫폼 클라이언트, pipelines/ 콘텐츠 흐름
- pipelines끼리 import 금지

## 명령
- 테스트: `uv run pytest`
- 게시/수집 시험: `uv run python -m pipelines.threads_post --dry-run`
- Threads 토큰 최초 발급/재발급: threads-auth-page 에서 코드 복사 → `uv run python -m channels.threads.get_token`
- Notion 속성 이름은 core/schema.py 와 docs/notion-schema.md 를 같이 고친다.

## 운영 메모
- 로컬에서 실제 게시(`--dry-run` 없이)는 GitHub Actions 예약 실행이 꺼져 있거나 겹치지 않을 때만 한다 (POSTING 점유는 원자적이지 않음).
- status=POSTING 으로 남은 글: Threads 앱에서 게시 여부 확인 → 게시됐으면 POSTED + 게시ID 입력, 안 됐으면 APPROVED 로 되돌림.
- FAILED + "network: 게시 여부 확인 필요": 위와 같이 확인 후 처리.
- 예약시각이 비어 있는 글은 게시되지 않는다.
