# 클라우드 렌더 운영 설계 (Actions + Google Drive + 텔레그램)

날짜: 2026-10-30 · 대상: 쇼츠(`pipelines/shopping_shorts`)와 드라마(`pipelines/ai_drama`)

## 목표

PC를 켜지 않고도 렌더한다.
- 사람은 그림을 Drive에 올리고, Notion에서 승인하고, GitHub `Run workflow`를 누른다.
- 결과 영상은 Drive에 올라가고, 텔레그램으로 알림이 온다.

## 결정

| 항목 | 결정 |
|---|---|
| 실행 | GitHub Actions `workflow_dispatch`만. 정기 확인(cron)은 없음 (private 저장소 무료 시간 절약) |
| 누르는 곳 | github.com 또는 GitHub 앱 → Actions → `render` → `Run workflow` |
| 입력 자료 | Drive `moruu/쇼츠/{content_id}/`, `moruu/롱폼/{content_id}/`, `moruu/음악/` |
| 결과 | 같은 자료 폴더에 `{content_id}.mp4`(+ 롱폼은 `.srt`), Notion `영상 링크` |
| 알림 | 텔레그램 봇 메시지 (보내기만 함) |
| 승인 | 사람만 `status=APPROVED`로 바꾼다 (기존 규칙). Claude는 DRAFT까지 |

## 사람 작업 흐름

1. Claude가 DRAFT를 만든다. `자료 폴더`가 비어 있으면 Claude가 로컬에서 `python -m pipelines.media_folders`를 돌려 Drive 폴더를 만들고, 링크를 Notion `자료 폴더`에 적는다. 워크플로 `할 일=폴더`로도 할 수 있다.
2. 사람이 `자료 폴더` 링크를 열고 그림(`01.png`…)과 `출처.txt`를 올린다. 휴대폰에서도 된다.
3. 사람이 Notion에서 status를 APPROVED로 바꾼다.
4. 사람이 `Run workflow`를 누른다.
   - 입력:
     - `할 일`: `렌더`(기본) / `폴더`
     - `대상`: `전체`(기본) / `쇼츠` / `롱폼`
     - `content_id`: 비우면 APPROVED 전부
5. 텔레그램 알림을 받고, 링크로 영상을 검토한다. YouTube 업로드는 [5] 단계에서 따로 다룬다.

## 워크플로 `.github/workflows/render.yml`

- `on: workflow_dispatch`, 입력 3개(위). `concurrency: render`로 같은 워크플로가 겹쳐 돌지 않게 한다(앞 실행이 끝날 때까지 기다림). `timeout-minutes: 120`.
- 단계:
  1. checkout, uv·Python 설치 (`threads.yml`과 같은 방식)
  2. 한글 글꼴 `fonts-noto-cjk` 설치 (`find_font`가 시스템 글꼴을 찾음)
  3. `actions/cache`로 `.cache/tts`를 복원한다. 키는 `tts-${{ github.run_id }}`, restore-keys는 `tts-`다.
  4. `할 일=폴더`: `python -m pipelines.media_folders`
  5. `할 일=렌더`: `대상`에 따라 아래 명령을 차례로 돌린다.
     - `python -m pipelines.shopping_shorts --from-drive [--content-id]`
     - `python -m pipelines.ai_drama --from-drive [--content-id]`
     - 하나가 실패해도 다음은 돌고, 마지막에 실패가 있었으면 워크플로를 실패로 끝낸다.
- Secrets:
  - 기존: `NOTION_TOKEN` 등 Notion DB·페이지 ID, `GOOGLE_TTS_API_KEY`
  - 새로: `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, `GDRIVE_REFRESH_TOKEN`, `GDRIVE_ROOT_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 렌더 시간은 첫 실행에서 재고, `docs/TODO-manual.md`에 적는다. 월 2,000분 무료 한도를 넘는지 그때 판단한다.

## 부품

### `channels/gdrive/` (새 패키지)
- **권한:** `https://www.googleapis.com/auth/drive` (전체).
  - 사람이 올린 파일을 읽고 같은 폴더에 써야 해서, `drive.file`(앱이 만든 파일만)로는 안 된다.
  - 이 토큰은 Drive 전체를 열 수 있으므로 Secrets에만 둔다. 출력이나 로그에 남기지 않는다.
  - moruu 전용 Google 계정을 쓰는 것도 권한다. 이 경우 폴더를 내 계정에 공유해서 본다.
- **토큰 발급:** `get_token.py`가 설치형 앱 OAuth(로컬 리디렉션)로 로그인해 refresh token을 `.env`에 쓴다.
  - OAuth 동의 화면을 '프로덕션'으로 바꿔야 토큰이 7일 만에 만료되지 않는다. 검증받지 않은 앱이라 로그인할 때 경고가 뜨는데, 개인용이므로 계속 진행한다.
  - 절차는 `docs/TODO-manual.md`에 적는다.
- **`client.py` — `DriveClient(client_id, secret, refresh_token, http)`**
  - access token은 refresh token으로 받아서 메모리에만 둔다.
  - 메서드:
    - `child(folder_id, name) -> id | None`
    - `ensure_folder(parent_id, name) -> id`
    - `list(folder_id) -> [DriveFile(id, name, mime, size)]`
    - `download(file_id, path)`
    - `upload(path, folder_id) -> web_url`
      - 이어 올리기(resumable) 방식이다.
      - 같은 이름 파일이 있으면 그 파일의 새 버전으로 올린다. 링크가 바뀌지 않는다.
  - 오류는 `DriveError(status, message)`로 낸다. 토큰은 메시지에 넣지 않는다.
- **`sync.py`**
  - `pull(drive, folder_id, dest)`: 폴더의 파일을 `dest`로 받는다. 하위 폴더와 `.mp4` 결과 파일은 건너뛴다. 크기가 같은 파일이 이미 있으면 받지 않는다.
  - `folder_path(drive, root_id, *names) -> id`: 경로를 따라가며 폴더를 찾거나 만든다.

### `channels/telegram/` (새 패키지)
- `client.py` — `Telegram(token, chat_id, http).send(text)`
  - `sendMessage`로 보낸다. 링크 미리보기는 끈다.
  - 알림 실패는 렌더 결과를 바꾸지 않는다. 경고 로그만 남기고, 토큰은 로그에 넣지 않는다.
- 설정이 없으면(로컬 등) 알림을 보내지 않고 로그로 대신한다.

### `pipelines/media_folders/` (새 패키지)
- 콘텐츠 DB에서 채널 `YT-쇼핑`·`YT-롱폼`이고 status가 DRAFT 또는 APPROVED인데 `자료 폴더`가 빈 페이지를 찾는다.
- 그런 페이지마다 `moruu/쇼츠|롱폼/{content_id}/` 폴더를 만들고, 링크를 `자료 폴더`에 적는다.
- 몇 개를 만들었는지 텔레그램으로 알린다.
- 이 패키지는 상태를 바꾸지 않는다.

### 렌더 파이프라인 변경 (쇼츠·드라마 같은 형태)
- `--from-drive` 옵션
  - 렌더 전에 `pull`로 받는다.
    - `자료 폴더` → `assets/{shorts|longform}/{content_id}/`
    - 드라마는 `moruu/음악/` → `assets/music/`도 받는다.
  - 받은 뒤의 흐름은 로컬과 같다.
- 업로드: `Uploader` 프로토콜(`upload(path) -> url`)을 주입한다.
  - `--from-drive`면 같은 자료 폴더에 올린다.
  - `--no-upload`이거나 Drive 설정이 없으면 업로드하지 않는다.
- `mark_rendered(post, link)`가 `영상 링크`를 적는다.
- 알림: `Notifier` 프로토콜(`send(text)`)을 주입한다. 글마다 한 번 보낸다.
  - 성공: `✅ {content_id} 렌더 완료 · {길이} · {링크}`
  - 실패: `❌ {content_id} 실패 · {오류 앞 300자}`
  - 렌더할 글이 없으면: `렌더할 글 없음 ({대상})` 한 번
- `assets/shorts`, `assets/longform`, `assets/music`은 계속 `.gitignore`. 로컬 렌더(`--from-drive` 없이)는 지금처럼 로컬 폴더를 쓴다.

### Notion·설정
- 콘텐츠 DB에 속성 2개를 추가한다.
  - `자료 폴더` (URL)
  - `영상 링크` (URL, 드라마 설계와 같음)
- `core/schema.py`와 `docs/notion-schema.md`를 같이 고친다.
- `core/config.py`:
  - `DriveSettings(client_id, client_secret, refresh_token, root_id)`
  - `TelegramSettings(token, chat_id)`
  - 모두 선택이고, 비면 해당 기능을 끈다.

## 오류 처리

| 실패 | 처리 |
|---|---|
| 자료 받기 (`DriveError`) | FAILED, `오류`에 `drive: …`, 알림 |
| 렌더 | 기존과 같음 (FAILED + `오류`), 알림 |
| 업로드 | FAILED, `오류`에 `upload: …`. 다시 실행하면 캐시 덕분에 빠름. 알림 |
| 알림 실패 | 경고 로그만 |
| Drive 토큰 만료·취소 | `drive: 401 …`. `get_token`을 다시 돌리고 Secret을 바꾸는 절차를 TODO-manual에 적음 |

## 테스트

- **`gdrive/client`**: `httpx.MockTransport`로 확인한다.
  - 토큰 갱신, 폴더 찾기·만들기
  - 목록 페이지 넘기기
  - 이어 올리기(세션 시작 → 업로드), 같은 이름이면 새 버전으로 올리기
  - 오류 메시지에 토큰이 없음
- **`gdrive/sync`**: 결과 파일·하위 폴더는 건너뜀, 같은 크기면 다시 받지 않음, 경로 만들기
- **`telegram`**: 요청 본문 확인, 실패해도 예외가 나지 않음
- **`media_folders`**:
  - `자료 폴더`가 빈 글만 처리
  - 채널별 상위 폴더 이름
  - status는 그대로
- **쇼츠·드라마 `__main__`**:
  - `--from-drive`면 pull 다음에 렌더
  - 업로드 링크가 `mark_rendered`로 전달됨
  - 실패 단계별 `오류` 접두어(`drive:`·`render:`·`upload:`)와 알림 내용
  - Uploader·Notifier가 없으면 로컬 동작이 지금과 같음 (기존 테스트 통과)
- **워크플로**: YAML은 직접 테스트하지 않는다. 시험 글 1개로 `Run workflow`를 실제로 돌려 확인한다.

## 구현 순서

1. 드라마 렌더 엔진 (`2026-10-30-drama-render-engine-design.md`), 로컬에서 완성
2. `channels/gdrive`, `channels/telegram`, `pipelines/media_folders`
3. 쇼츠·드라마에 `--from-drive`, 업로드, 알림 붙이기
4. `render.yml`, Secrets 등록, 시험 실행
