# 클라우드 렌더 운영 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 쇼츠와 드라마를 GitHub Actions `Run workflow`로 렌더한다.
- 자료는 Drive에서 받고, 결과는 Drive에 올린다.
- 끝나면 텔레그램으로 알린다.

**Architecture:**
- **바깥 서비스 클라이언트 (`channels/`)**
  - `channels/gdrive`: Drive REST, httpx 직접 호출
  - `channels/telegram`: Bot API 메시지 보내기
- **흐름 (`pipelines/`)**
  - `pipelines/media_folders`: DRAFT·APPROVED 글마다 자료 폴더를 만든다.
  - 쇼츠·드라마 `__main__`에 `--from-drive`를 추가한다. 동작:
    1. 렌더 전에 Drive 자료를 `assets/…`로 받는다.
    2. 받은 다음의 흐름은 지금과 같다.
    3. 업로드·알림은 주입받은 함수로 한다.

**Tech Stack:** Python 3.12+, httpx, Google Drive API v3 (REST), Telegram Bot API, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-10-30-cloud-render-ops-design.md`

## Global Constraints

- **실행:** 테스트는 `.venv/Scripts/python.exe -m pytest -q`로 돌린다(PATH에 `uv` 없음). Actions에서는 `uv run`을 쓴다.
- **키·토큰:** 출력·커밋·로그하지 않는다.
  - Telegram 토큰은 URL 경로에 들어간다. 그래서 오류 메시지에 URL·httpx 예외 문자열을 넣지 않는다.
  - Drive 오류 메시지에는 HTTP 상태와 응답의 `error.message`만 넣는다.
- **import:** pipelines끼리 import하지 않는다. 공통 코드는 `channels/`·`core/`에 둔다.
- **Notion 속성:** `core/schema.py`와 `docs/notion-schema.md`를 같이 고친다.
- **상태:** `status=APPROVED`는 사람만 바꾼다. `media_folders`는 상태를 바꾸지 않는다.
- **기존 동작:** 쇼츠·드라마 기존 테스트는 그대로 통과해야 한다. `--from-drive`가 없으면 동작이 지금과 같다.
- **커밋:** 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- **Drive:**
  - 권한 범위: `https://www.googleapis.com/auth/drive`
  - 폴더 구조: 루트 `GDRIVE_ROOT_ID` 아래 `쇼츠/{content_id}`, `롱폼/{content_id}`, `음악`
  - 링크 형식: 파일 `https://drive.google.com/file/d/{id}/view`, 폴더 `https://drive.google.com/drive/folders/{id}`
- **알림 문구:**
  - 성공: `✅ {content_id} 렌더 완료 · {링크}`
  - 실패: `❌ {content_id} 실패 · {사유 앞 300자}`
  - 폴더: `📁 자료 폴더 {n}개 만듦`
- **스펙 보완:** 스펙에 없던 세 가지를 더한다. TODO-manual 6-4에 이미 적었다.
  - `channels.gdrive.get_token --check`
  - `channels.telegram --chat-id`
  - `channels.telegram "글"`

## 파일 구조

| 파일 | 책임 |
|---|---|
| `channels/telegram/__init__.py`, `client.py`, `__main__.py` (새) | `Telegram(token, chat_id).send(text) -> bool`, `chat_id_from_updates()`, CLI |
| `channels/gdrive/__init__.py`, `client.py` (새) | `DriveClient`: 토큰 갱신, 찾기·만들기·목록·받기·올리기(이어 올리기, 같은 이름이면 새 버전) |
| `channels/gdrive/sync.py` (새) | `folder_path`, `pull`, `upload_outputs` |
| `channels/gdrive/get_token.py` (새) | 로컬 리디렉션 OAuth(PKCE) → `.env`에 `GDRIVE_REFRESH_TOKEN`, `--check` |
| `core/schema.py`, `core/models.py`, `core/notion_store.py`, `core/config.py` (수정) | `자료 폴더`, `Post.channel`·`Post.media_folder`, `missing_media_folders()`, `set_media_folder()`, `DriveSettings`, `TelegramSettings` |
| `pipelines/media_folders/__init__.py`, `__main__.py` (새) | 자료 폴더 만들기 |
| `pipelines/shopping_shorts/__main__.py` (수정) | `run(..., fetch_media, uploader, notifier)`, `--from-drive`, `--no-upload` |
| `pipelines/ai_drama/__main__.py` (수정) | `run(..., fetch_media)`, `--from-drive`, `--no-upload`, 음악 받기 |
| `.github/workflows/render.yml` (새) | 수동 실행 워크플로 |
| `docs/notion-schema.md`, `CLAUDE.md` (수정) | 속성·명령 |

---

### Task 1: 텔레그램 알림

**Files:** Create `channels/telegram/{__init__,client,__main__}.py`. Test `tests/channels/test_telegram.py`

**Interfaces:**
- Produces:
  - `Telegram(token: str, chat_id: str, http: httpx.Client | None = None)`
  - `.send(text) -> bool`: 실패해도 예외를 내지 않는다. 경고 로그만 남기고 False를 돌려준다.
  - `.latest_chat_id() -> str | None`: `getUpdates`의 마지막 메시지 chat.id

- [ ] **Step 1: 테스트**
  - `send`의 요청을 확인한다.
    - 경로: `/bot{token}/sendMessage`
    - JSON: `{"chat_id": "42", "text": "가", "disable_web_page_preview": True}`
    - 응답 200이면 True를 돌려준다.
  - 실패 응답을 확인한다.
    - 400 `{"ok": false, "description": "chat not found"}`이면 False를 돌려준다.
    - 경고 로그에 토큰 문자열이 없어야 한다(`caplog`).
  - 연결 오류: transport가 `httpx.ConnectError`를 내면 False를 돌려준다. 이때도 로그에 토큰이 없어야 한다.
  - `latest_chat_id`: getUpdates 결과 `[{message:{chat:{id:1}}},{message:{chat:{id:2}}}]`이면 `"2"`, 결과가 비면 None
- [ ] **Step 2: 실패 확인 → 구현.** `base_url="https://api.telegram.org"`. 오류 로그는 `"텔레그램 알림 실패: %s"`에 `description` 또는 예외 클래스 이름만 넣는다.
- [ ] **Step 3: `__main__`**
  - `--chat-id`: `.env`의 토큰으로 `latest_chat_id()`를 얻어 `update_env_file(ENV, {"TELEGRAM_CHAT_ID": id})`로 저장한다. `channels.threads.token`의 함수를 재사용한다.
  - 인자가 글이면 `send` 결과에 따라 `ok` / `실패`를 출력한다.
- [ ] **Step 4: 통과 확인 → 커밋** `feat: 텔레그램 알림`

### Task 2: Drive 클라이언트

**Files:** Create `channels/gdrive/{__init__,client}.py`. Test `tests/channels/test_gdrive_client.py`

**Interfaces:**
- Produces:
  - `DriveError(status: int, message: str)`
  - `DriveFile(id, name, mime, size: int | None)`
  - `DriveClient(client_id, client_secret, refresh_token, http: httpx.Client | None = None)`
  - 메서드:
    - `child(parent_id, name) -> DriveFile | None`
    - `ensure_folder(parent_id, name) -> str`
    - `list(folder_id) -> list[DriveFile]`
    - `download(file_id, dest: Path)`
    - `upload(path: Path, folder_id: str, chunk: int = 8 * 1024 * 1024) -> str`: 파일 id를 돌려준다.
    - `meta(file_id) -> DriveFile`
  - `FOLDER_MIME = "application/vnd.google-apps.folder"`, `file_url(id)`, `folder_url(id)`

- [ ] **Step 1: 테스트** (`httpx.MockTransport` 하나로 요청을 경로별로 나눠 응답)
  - 첫 API 호출 전에 `POST https://oauth2.googleapis.com/token`을 정확히 1번 부른다.
    - 폼: `grant_type=refresh_token`, `client_id`, `client_secret`, `refresh_token`
    - 이후 요청 헤더는 `Authorization: Bearer AT`
  - `child`
    - 요청: `GET /drive/v3/files`, `q`에 `'P' in parents and name = '이름' and trashed = false`
    - 이름에 `'`가 있으면 `\'`로 이스케이프한다.
  - `ensure_folder`: 있으면 그 id를 돌려준다. 없으면 `POST /drive/v3/files`로 `{"name","mimeType":FOLDER,"parents":[P]}`를 보내 새 id를 받는다.
  - `list`: `nextPageToken`으로 페이지를 넘긴다(두 번 호출해서 합침). `size`는 문자열이므로 int로 바꾼다.
  - `download`: `GET /drive/v3/files/F?alt=media` 내용을 파일로 쓴다.
  - `upload` (새 파일)
    1. `POST /upload/drive/v3/files?uploadType=resumable`, 본문 `{"name","parents":[P]}`. 응답 헤더 `Location`이 세션 URL이다.
    2. `chunk=4`, 10바이트 파일이면 PUT이 3번 간다.
       - `Content-Range: bytes 0-3/10`, `bytes 4-7/10` → 308
       - `bytes 8-9/10` → 200 `{"id":"NEW"}`
    3. `"NEW"`를 돌려준다.
  - `upload` (같은 이름 있음): `PATCH /upload/drive/v3/files/OLD?uploadType=resumable`, 본문 `{}` → 세션 → PUT → `"OLD"`
  - 오류
    - 403 `{"error":{"message":"insufficient"}}` → `DriveError(403, "insufficient")`
    - 토큰 갱신 실패 400 `{"error":"invalid_grant"}` → `DriveError(400, "invalid_grant")`
    - 메시지에 refresh token이나 secret이 없어야 한다.
- [ ] **Step 2: 실패 확인 → 구현**
  - access token은 메모리에만 둔다. 401이면 한 번만 갱신하고 다시 시도한다.
  - `size` 필드가 없으면(폴더) None으로 둔다.
- [ ] **Step 3: 통과 확인 → 커밋** `feat: Google Drive 클라이언트 (이어 올리기)`

### Task 3: 동기화 helper와 토큰 발급

**Files:** Create `channels/gdrive/{sync,get_token}.py`. Test `tests/channels/test_gdrive_sync.py`, `tests/channels/test_gdrive_token.py`

**Interfaces:**
- Consumes: `DriveClient` (Task 2)
- Produces:
  - `folder_path(drive, root_id, *names) -> str`: `ensure_folder`를 차례로 부른다.
  - `pull(drive, folder_id, dest: Path) -> list[str]`: 받은 파일 이름 목록
    - 폴더와 `.mp4`·`.srt`(결과 파일)는 건너뛴다.
    - 같은 크기의 로컬 파일이 있으면 받지 않는다.
  - `upload_outputs(drive, folder_id, paths: list[Path]) -> str`: 있는 파일만 올리고, 첫 파일의 `file_url`을 돌려준다.
  - `get_token.auth_url(client_id, redirect, challenge) -> str`, `get_token.exchange(http, client_id, secret, code, redirect, verifier) -> str`(refresh token)

- [ ] **Step 1: 테스트**
  - `pull`: 가짜 drive(list·download 기록)로 확인한다.
    - `01.png`(크기 3, 로컬 없음)는 받는다.
    - `02.png`(로컬에 같은 크기 있음)는 건너뛴다.
    - 하위 폴더, `YT-1.mp4`, `YT-1.srt`는 건너뛴다.
  - `upload_outputs`: 없는 `.srt`는 건너뛴다. 돌려주는 값은 mp4 링크다.
  - `folder_path`: `ensure_folder(root,"롱폼")`, `ensure_folder(that,"YT-1")` 순서로 부른다.
  - `auth_url`에 들어가야 할 것: `access_type=offline`, `prompt=consent`, scope drive, `code_challenge_method=S256`, `redirect_uri`
  - `exchange`: 요청 폼에 `grant_type=authorization_code`, `code_verifier`가 들어간다. 응답의 `refresh_token`을 돌려주고, 없으면 `DriveError`를 낸다.
- [ ] **Step 2: 구현**
  - `get_token.main`
    1. `.env`의 `GDRIVE_CLIENT_ID/SECRET`을 읽는다.
    2. `http.server`를 `127.0.0.1:0`에서 연다.
    3. `webbrowser.open(auth_url)`로 로그인 화면을 연다.
    4. 리디렉션으로 `code`를 받고 브라우저에 "완료 — 창을 닫으세요"를 보여 준다.
    5. `exchange`로 refresh token을 받아 `update_env_file`로 저장하고 `저장됨: GDRIVE_REFRESH_TOKEN`을 출력한다.
  - `--check`: `DriveClient(...).meta(GDRIVE_ROOT_ID)` 결과로 `ok: {name} 폴더 접근됨`을 출력한다.
  - 실패하면 토큰 없이 `실패: {status} {message}`를 출력한다.
- [ ] **Step 3: 통과 확인 → 커밋** `feat: Drive 자료 받기·결과 올리기, 토큰 발급`

### Task 4: Notion `자료 폴더`와 설정

**Files:** Modify `core/schema.py`, `core/models.py`, `core/notion_store.py`, `core/config.py`, `docs/notion-schema.md`. Test `tests/core/*`

**Interfaces:**
- Produces:
  - `S.MEDIA_FOLDER = "자료 폴더"`
  - `Post.channel: str = ""`, `Post.media_folder: str = ""`
  - `NotionStore.missing_media_folders() -> list[Post]`
    - 채널 ∈ {YT-쇼핑, YT-롱폼}, status ∈ {DRAFT, APPROVED}, `자료 폴더` is_empty
  - `NotionStore.set_media_folder(post, url)`
  - `DriveSettings.from_env(env) -> DriveSettings | None`: 네 값이 모두 있어야 객체를 돌려주고, 하나라도 비면 None
  - `TelegramSettings.from_env(env) -> TelegramSettings | None`
- [ ] **Step 1: 테스트**
  - 필터 JSON 구조: `and` 안에 채널 `or` 2개, status `or` 2개, `{"property":"자료 폴더","url":{"is_empty":true}}`
  - `set_media_folder`는 `{"자료 폴더": {"url": u}}`
  - `parse_post`가 채널과 자료 폴더를 읽는다.
  - 설정은 값이 일부만 있으면 None이다.
- [ ] **Step 2: 구현 → 통과 → Notion에 `자료 폴더` URL 속성 추가 (MCP) → docs 갱신 → 커밋** `feat: Notion 자료 폴더 속성, Drive·텔레그램 설정`

### Task 5: 자료 폴더 만들기 파이프라인

**Files:** Create `pipelines/media_folders/{__init__,__main__}.py`. Test `tests/pipelines/test_media_folders.py`

**Interfaces:**
- Produces: `run(store, make_folder: Callable[[Post], str], log, notifier=None) -> int`
  - `make_folder(post)`가 링크를 돌려준다.
  - `CHANNEL_DIR = {"YT-쇼핑": "쇼츠", "YT-롱폼": "롱폼"}`
- [ ] **Step 1: 테스트**
  - 글 2개면 `make_folder`를 2번 부르고, `set_media_folder`를 2번 부르고, 알림은 `📁 자료 폴더 2개 만듦`이다.
  - 0개면 알림이 없다.
  - `make_folder`가 `DriveError`를 내면 그 글만 건너뛰고 경고를 남긴다. 반환값은 1이다.
- [ ] **Step 2: 구현** — `main`:
  1. Notion·Drive 설정을 읽는다. Drive 설정이 없으면 오류 메시지를 출력하고 1을 돌려준다.
  2. `make_folder = folder_url(folder_path(drive, root, CHANNEL_DIR[post.channel], post.content_id))`
  3. 텔레그램 설정이 있으면 알림을 보낸다.
- [ ] **Step 3: 커밋** `feat: 쇼츠·롱폼 자료 폴더 자동 생성`

### Task 6: 쇼츠·드라마에 Drive·알림 연결

**Files:** Modify `pipelines/shopping_shorts/__main__.py`, `pipelines/ai_drama/__main__.py`. Test `tests/pipelines/test_shorts_pipeline.py`, `tests/pipelines/test_drama_pipeline.py`

**Interfaces:**
- 두 `run` 모두 `fetch_media: Callable[[Post], None] | None = None`을 추가로 받는다. 이 함수는 글을 검사하기 전에 부른다.
  - `DriveError`나 `httpx.HTTPError`가 나면 `drive: …`로 FAILED 처리하고 알림을 보낸다.
  - dry-run에서도 부른다(받아서 검사해 보기). 다만 dry-run에서는 FAILED로 바꾸지 않고 로그만 남긴다.
- 쇼츠 `run`에 `uploader`, `notifier`를 드라마와 같은 의미·문구로 추가한다.
  - `store.mark_rendered(post, link)`
  - 오류 접두어: `render:`(기존 유지), `upload:`(새)
- `main`(둘 다)
  - `--from-drive`: Drive 설정이 필수다.
    - `fetch_media`는 `pull(drive, folder_path(root, 쇼츠|롱폼, cid), assets/cid)`를 한다.
    - 드라마는 렌더를 시작하기 전에 `pull(drive, folder_path(root, "음악"), MUSIC)`을 한 번 한다.
  - 업로드: Drive 설정이 있고 `--no-upload`가 아니면 `upload_outputs(drive, folder_path(...), [mp4, srt])`를 한다.
  - 알림: 텔레그램 설정이 있으면 `Telegram.send`, 없으면 로그로 대신한다.
- [ ] **Step 1: 테스트**
  - 쇼츠: uploader의 링크가 `mark_rendered`로 전달되고, 알림 문구가 맞는다.
  - 쇼츠: uploader가 OSError를 내면 `upload: …`로 기록된다.
  - 쇼츠·드라마: `fetch_media`가 `DriveError(403,"x")`를 내면 `drive: [403] x`로 기록되고, 렌더는 호출되지 않는다.
  - 기존 쇼츠 Store 가짜의 `mark_rendered(self, post)` 시그니처를 `link=None`으로 넓힌다.
- [ ] **Step 2: 구현 → 전체 테스트 → 커밋** `feat: 쇼츠·드라마 --from-drive, 업로드·텔레그램 알림`

`DriveError.__str__`은 `[{status}] {message}`로 한다. Task 2에서 정의한다.

### Task 7: 워크플로와 문서

**Files:** Create `.github/workflows/render.yml`. Modify `CLAUDE.md`

- [ ] **Step 1: `render.yml`**
```yaml
name: render

on:
  workflow_dispatch:
    inputs:
      task:
        description: "렌더 / 폴더"
        default: 렌더
        type: choice
        options: [렌더, 폴더]
      target:
        description: "전체 / 쇼츠 / 롱폼"
        default: 전체
        type: choice
        options: [전체, 쇼츠, 롱폼]
      content_id:
        description: "비우면 APPROVED 전부"
        default: ""
        type: string

concurrency:
  group: render
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    env:
      NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
      NOTION_DB_CONTENT: ${{ secrets.NOTION_DB_CONTENT }}
      NOTION_DB_METRICS: ${{ secrets.NOTION_DB_METRICS }}
      NOTION_DB_FAILURES: ${{ secrets.NOTION_DB_FAILURES }}
      NOTION_PAGE_LEXICON: ${{ secrets.NOTION_PAGE_LEXICON }}
      GOOGLE_TTS_API_KEY: ${{ secrets.GOOGLE_TTS_API_KEY }}
      TTS_RATE: ${{ secrets.TTS_RATE }}
      TTS_VOICE: ${{ secrets.TTS_VOICE }}
      TTS_VOICE_MALE: ${{ secrets.TTS_VOICE_MALE }}
      GDRIVE_CLIENT_ID: ${{ secrets.GDRIVE_CLIENT_ID }}
      GDRIVE_CLIENT_SECRET: ${{ secrets.GDRIVE_CLIENT_SECRET }}
      GDRIVE_REFRESH_TOKEN: ${{ secrets.GDRIVE_REFRESH_TOKEN }}
      GDRIVE_ROOT_ID: ${{ secrets.GDRIVE_ROOT_ID }}
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
      TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
      INPUT_TASK: ${{ inputs.task }}
      INPUT_TARGET: ${{ inputs.target }}
      INPUT_ID: ${{ inputs.content_id }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: sudo apt-get update -q && sudo apt-get install -y -q fonts-noto-cjk
      - run: uv sync --frozen
      - uses: actions/cache@v4
        with:
          path: .cache/tts
          key: tts-${{ github.run_id }}
          restore-keys: tts-
      - name: 폴더
        if: inputs.task == '폴더'
        run: uv run python -m pipelines.media_folders
      - name: 렌더
        if: inputs.task == '렌더'
        run: |
          ARGS="--from-drive"
          if [ -n "$INPUT_ID" ]; then ARGS="$ARGS --content-id $INPUT_ID"; fi
          FAIL=0
          if [ "$INPUT_TARGET" != "롱폼" ]; then uv run python -m pipelines.shopping_shorts $ARGS || FAIL=1; fi
          if [ "$INPUT_TARGET" != "쇼츠" ]; then uv run python -m pipelines.ai_drama $ARGS || FAIL=1; fi
          exit $FAIL
```
- 비어 있는 Secret(`TTS_RATE` 등)은 빈 문자열이 된다. 기존 설정 코드는 `or` 기본값을 쓰므로 괜찮다.
- 렌더 시간을 아끼려고 pytest는 이 워크플로에서 돌리지 않는다. 테스트는 threads 워크플로와 로컬에서 돈다.
- [ ] **Step 2: YAML 문법 확인**
  - `PY -c "import yaml"`이 없으면 건너뛴다.
  - 대신 들여쓰기를 눈으로 보고, 키 이름이 `threads.yml`과 맞는지 확인한다.
- [ ] **Step 3:** `CLAUDE.md` 명령에 추가: `--from-drive`, `python -m pipelines.media_folders`, Actions `render`(수동 실행)
- [ ] **Step 4: 커밋** `feat: render 워크플로 (수동 실행)`

### Task 8: 확인 (사람 준비가 끝난 뒤)

- [ ] 키가 준비된 것만 로컬에서 확인한다(TODO-manual 6-4 A·B).
  - `channels.gdrive.get_token --check`
  - `channels.telegram "시험"`
  - `pipelines.media_folders`
  - `pipelines.ai_drama --from-drive --dry-run`
- [ ] 키가 아직 없으면 여기서 멈추고, 사람이 할 일 목록을 알린다.
