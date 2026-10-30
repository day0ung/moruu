# AI 대본 에이전트 설계 (기획 → 대본 DRAFT)

날짜: 2026-10-30 · 원 계획서: `docs/ai-agent-plan.md` · 조사: `docs/research/free-llm-compare.md`, `docs/research/oss-references.md`

## 결정

| 항목 | 결정 |
|---|---|
| AI 모델 | 무료로 시작. 1순위 Gemini API 무료 등급, 2순위 OpenRouter `:free`. OpenAI 호환 `/chat/completions`를 httpx로 직접 호출. 서비스·역할별 모델은 설정으로 바꾼다 |
| 사람 확인 | 기획안 3개 중 하나를 사람이 승인한 뒤 대본을 쓴다 |
| 시리즈 | 고정 시리즈. 인물은 시리즈 바이블 표에서 가져온다 |
| 구조 | 단순한 Python 순서 실행. 진행 상태는 Notion 페이지 자체(이미 붙은 챕터 다음부터 이어 쓴다) |
| 상태 | `기획 → (사람) 기획승인 → (AI) DRAFT → (사람) APPROVED → RENDERED` |

## Notion

- 콘텐츠 DB
  - `status`에 `기획`, `기획승인`을 추가한다.
  - `회차 요약`(rich_text)을 추가한다. 갈등·결말·반전 3줄이고, 다음 기획 때 반복을 피하는 데 쓴다.
- 시리즈 페이지 본문
  - `## 세계관`: 문단·목록 글자를 그대로 읽는다.
  - `## 금지·주의`: 위와 같이 읽는다.
  - 인물 표: 인물, 목소리, 높낮이, 빠르기, 자막색, 나이·성격, 그림 설명
- 시리즈 DB ID는 `.env`의 `NOTION_DB_SERIES`(87c37794…)에 둔다. 기획 워크플로가 시리즈를 이름으로 찾는다.
- 기획 페이지
  - 속성: 채널 YT-롱폼, 시리즈 연결, status 기획, content_id `YT-롱폼-YYYYMMDD-HHMM-n`, 메모 = 소재
  - 본문은 토글 `📋 기획안` 하나다. 렌더는 맨 위 블록만 읽으므로 토글 안은 무시된다.
  - 토글 안 내용
    - `### 제목 후보`: 목록 5개
    - `### 썸네일 문구`
    - `### 시놉시스`
    - `### 이번 회차 인물`: 목록 `이름 — 역할·나이·성격`
    - `### 챕터 N · 제목` × 8: 목록(사건·감정·복선)
    - `### 반전과 복선 회수`
- 대본을 쓴 뒤 같은 페이지
  - `▸ 🔍 검수 기록` 토글
  - 챕터마다 `# 챕터 N · 제목`(제목1, 렌더는 무시하고 이어 쓰기 기준으로 쓴다)
  - 장면마다 아래 블록이 붙는다.
    - `## 장면 K · 제목 #음악 태그`
    - 콜아웃 `🖼 KK.png — 그림 프롬프트`
    - 대사 문단
- 새 인물: `이번 회차 인물` 중 바이블에 없는 이름은 대본을 쓰기 전에 시리즈 인물 표에 줄로 추가한다.
  - 목소리는 설명에 남성 단서(남·아들·아버지·할아버지·남편·형·오빠·삼촌)가 있으면 `ko-KR-Neural2-C`, 아니면 `ko-KR-Neural2-A`
  - 나이·성격 칸에 설명을 넣는다.

## 부품

- `channels/llm/client.py`
  - `Provider(name, base_url, key, models{role: model})`
  - `LLM(providers).chat(messages, role) -> Reply(text, provider, model, tokens)`
  - 429·5xx면 다음 서비스로 넘어간다. 모두 실패하면 `LLMQuotaError`, 그 밖의 오류는 `LLMError`.
  - `chat_json`: 응답에서 JSON을 꺼내고, 실패하면 1번 더 요청한다.
- `core/config.py`의 `LLMSettings`
  - `LLM_PROVIDERS=gemini,openrouter`
  - 키: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
  - 역할별 모델 덮어쓰기: `GEMINI_MODEL_{PLAN|WRITE|REVIEW|LIGHT}` 등
  - 기본 모델
    - gemini: plan·write·review = `gemini-3.8-flash`, light = `gemini-3.5-flash-lite`
    - openrouter: 모두 `google/gemma-4-31b-it:free`
- `pipelines/ai_story/`
  - `prompts/*.md` (`string.Template`, `$변수`)
  - `context.py`: 시리즈 맥락 (세계관·금지·인물·지난 회차 요약)
  - `plan_doc.py`: 기획안 JSON → Notion 블록, 토글 글자 → 챕터 목록·이번 회차 인물
  - `script_doc.py`: 장면 JSON → Notion 블록, 페이지의 이미 쓴 챕터 수
  - `agents.py`: `plan(n=3)`, `write_chapter`, `review_chapter`, `image_prompts`, `summarize`
  - `checks.py`: 기계 검사
    - 화자가 바이블·이번 회차 인물에 있는지
    - `narration.problems`, 금지어
    - 챕터 분량: 목표 = 30분 × 258자/분 ÷ 8, ±40%
  - `__main__.py`: `plan --series 이름 [--topic 소재]`, `write [--content-id ID]`
- `core/notion_store.py`
  - 페이지 만들기, 블록 붙이기(100개씩)
  - 시리즈 찾기, 시리즈 회차 요약 목록
  - 표에 줄 추가 (`Table.id` 추가)
  - 상태·요약 바꾸기
- `.github/workflows/story.yml`: 수동 실행. 입력은 `할 일`(기획/대본), `시리즈`, `소재`, `content_id`.

## 흐름

- **기획:** 시리즈 맥락 + 소재 → 기획안 3개(JSON, 서로 다른 갈등·결말, 지난 회차와 겹치지 않게) → 페이지 3개 → 텔레그램 `📝 기획안 3개`
- **대본:** `기획승인` 글마다 아래 순서로 진행한다.
  1. 토글 글자를 읽는다(사람이 고친 그대로).
  2. 새 인물을 바이블에 추가한다.
  3. 이미 쓴 챕터 다음부터 챕터마다 작성 → 기계 검사 + AI 검수(최대 3회 수정) → 그림 프롬프트 → 페이지에 붙이기 → 검수 기록
  4. 마지막에 회차 요약을 만들고, status를 DRAFT로 바꾸고, 텔레그램 `✍️ … 대본 DRAFT (8챕터, 약 N자 ≈ M분)`
  - 3회 수정해도 통과하지 못하면 마지막 버전을 쓰고, 검수 기록에 `⚠ 검수 미통과`를 남긴다.
  - 한도 오류(`LLMQuotaError`)가 나면 거기서 멈춘다. status는 기획승인 그대로 두고 `⏸ 챕터 N에서 멈춤`을 알린다. 다음 실행 때 이어서 쓴다.
- **프롬프트 규칙**
  - 실존 인물·기업·상표를 쓰지 않는다.
  - 사실처럼 보이는 통계나 의학·법률 단정을 하지 않는다.
  - 금지어(최고·필수·무조건·혁신적)를 쓰지 않는다.
  - 화자는 주어진 인물만 쓴다.
  - 대사 안 특수 표기는 `[쉼 N]`만 쓴다.

## 범위 밖

그림·영상 생성 API, YouTube 업로드, 성과 수집, 쇼츠 대본 생성.
