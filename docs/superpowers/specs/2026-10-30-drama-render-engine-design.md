# 시니어 AI 드라마 렌더 엔진 설계

날짜: 2026-10-30 · 범위: 롱폼 파이프라인 [4] 편집 + [3] 중 TTS·배경음악. 로컬에서 완성한다.
Actions 실행·Drive 입출력·텔레그램 알림은 `2026-10-30-cloud-render-ops-design.md`가 다룬다.

## 목표

Notion에 쓴 에피소드 대본(내레이션 + 인물 대사)과 장면 그림·음악 폴더로 가로 1920×1080 영상(`.mp4`)과 자막(`.srt`)을 만든다.
- 사람은 대본 쓰기·그림 준비·최종 검토만 한다.
- 대사 한 줄을 고치면 그 줄만 TTS를 다시 부르고, 바뀐 장면만 다시 렌더한다.

범위 밖: 스토리 생성([2]), 그림 생성([3]), YouTube 업로드·썸네일([5]), 성과 수집([6]), 효과음, 장면 안 그림 바꾸기, 겹침 전환, 쇼츠를 새 렌더러로 옮기기.

## 결정 요약

| 항목 | 결정 |
|---|---|
| 화자 | 내레이션 + 인물 대사. 인물마다 목소리 |
| 인물 정의 | Notion 시리즈 DB의 바이블 표 |
| TTS | Google Cloud TTS로 시작, 바꿔 끼울 수 있게. 감정 표기 `이름(감정):`는 지금은 기록만. 후보 비교: `docs/drama-tts-compare.md` |
| 그림 | 장면 하나에 그림 1장, 천천히 확대 |
| 전환 | 장면 사이 0.3초 어두워졌다 밝아짐 |
| 배경음악 | 장면 제목 태그 `#음악 잔잔`. 태그 없으면 앞 곡 이어 감. 말할 때 줄이고, 곡이 바뀌면 서서히 |
| 자막 | 한 줄, 화면 아래, 인물마다 색 |
| 구조 | 대본 → `timeline.json` → 렌더 (줄 단위 TTS 캐시, 장면 조각 캐시) |
| 결과 보관 | 로컬 `out/drama/`. Drive 업로드는 운영 설계에서 `Uploader`를 주입해 붙인다 |

## 1. Notion 구조와 대본 형식

### 시리즈 DB (새로 만듦)
- 페이지 하나가 시리즈 하나다.
- 본문의 표(첫 줄은 머리글)가 인물 바이블이다.

| 인물 | 목소리 | 높낮이 | 빠르기 | 자막색 | 나이·성격 | 그림 설명 |
|---|---|---|---|---|---|---|
| 내레이션 | ko-KR-Neural2-A | 0 | 0.95 | 흰색 | | |
| 시어머니 | ko-KR-Neural2-A | -4 | 0.9 | 노랑 | 68세, 말수 적음 | 회색 단발 |
| 아들 | ko-KR-Neural2-C | 0 | 1.0 | 하늘 | 38세 | |

- `내레이션` 줄이 내레이터다. 표에 없으면 검사 오류.
- 표의 칸은 머리글 이름으로 찾는다. 칸 순서는 바뀌어도 된다.
- 높낮이: 반음 단위, -20~20. 비우면 0.
- 빠르기: 0.25~4.0. 비우면 설정의 `TTS_RATE`.
- 자막색: 이름(흰색·노랑·하늘·연두·분홍·주황·보라) 또는 `#RRGGBB`. 비우면 내레이션은 흰색, 인물은 표 순서대로 팔레트에서 고른다.
- `나이·성격`, `그림 설명`은 렌더에 쓰지 않는다. [2] 대본 생성과 [3] 그림 생성에서 쓴다.

### 콘텐츠 DB 변경
- `시리즈`: 시리즈 DB를 가리키는 연결 속성.
- `영상 링크`: Drive 파일 주소(URL 속성).
- 채널 `YT-롱폼`(이미 있음). 흐름은 쇼츠와 같다: DRAFT → (사람) APPROVED → 렌더 → RENDERED. 실패하면 FAILED + `오류`.
- `core/schema.py`와 `docs/notion-schema.md`를 같이 고친다.

### 에피소드 본문
```
## 장면 1 · 저녁 식탁 #음악 잔잔
그날 저녁, 시어머니는 말없이 상을 차렸다.
시어머니(서운하게): 너희 이번 주말에 올 거니?
아들: 회사 일이 좀 바빠서요… [쉼 0.5]
```
- **장면:** 제목 2(`heading_2`) 블록이 새 장면을 연다.
  - 제목에서 `#음악 X` 태그를 빼고 남은 글자가 장면 이름이다.
  - 장면 번호는 1부터 차례로 매긴다.
  - 첫 장면 제목 앞에 나온 문단은 검사 오류("장면 제목 전에 대사").
- **대사 줄:** 문단 블록 안의 한 줄(`\n`)이 대사 한 줄이고, 빈 줄은 건너뛴다.
  - `^([^\s:()]{1,8})(?:\(([^)]*)\))?:\s*(.+)$`에 맞고, 이름이 바이블에 있으면 그 인물의 대사다. 괄호 안은 감정이다.
  - 위 형태인데 이름이 바이블에 없으면 검사 오류("인물 'X' 바이블에 없음").
  - 나머지 줄은 모두 내레이션이다.
- **대사 안 문법:** 쇼츠와 같다. `{3M|쓰리엠}` 읽는 법, `[쉼 0.5]` 쉼, 발음 사전(`NOTION_PAGE_LEXICON`).
- **무시하는 블록:** 그 밖의 블록(콜아웃·인용·코드·제목1·3)은 메모로 보고 무시한다.

### 미디어 폴더
- **장면 그림:** `assets/longform/{content_id}/01.png`처럼 장면 번호로 붙인다(`.png/.jpg/.jpeg/.webp`).
  - 출처는 같은 폴더의 `출처.txt`에 적는다. 형식은 쇼츠와 같다: `03: url`, 번호 없는 줄은 기본 출처.
- **음악:** `assets/music/{태그}.mp3`(또는 `.m4a/.wav`).
  - 출처는 `assets/music/출처.txt`에 `태그: 출처` 형식으로 적는다.
- 두 폴더 모두 `.gitignore`에 넣는다.

### 렌더 전 검사 (하나라도 걸리면 렌더하지 않음)
- 장면이 없음
- 장면 제목 전에 대사가 있음
- 대사가 없는 장면
- 바이블 문제: 시리즈 연결이 없음, 표가 없음, `내레이션` 줄이 없음, 목소리가 빈 인물, 높낮이·빠르기·자막색 형식 오류
- 바이블에 없는 인물 이름
- 그림이 없는 장면, 출처가 없는 그림
- 파일이 없는 음악 태그, 출처가 없는 음악
- 그림 번호에 해당하는 장면이 없음
- 읽는 법·쉼 형식 오류 (`narration.problems`)
- 금지어 (`core.safety.banned_words`)

## 2. 부품

```
Notion ─▶ pipelines/ai_drama/script.py   본문 + 바이블 → Episode
                │
                ▼
        pipelines/ai_drama/build.py     Episode + TTS → Timeline
                │                        (channels/tts/cache 로 줄 단위 재사용)
                ▼
        channels/video/render.py        Timeline → 장면 조각 → 이어 붙이기 → 음악 섞기
                │
                ▼
        out/drama/{id}.mp4 · .srt · .timeline.json ──▶ (운영 설계) Drive 업로드
```

### 공통 (`channels/`, `core/`)
- `channels/tts/google.py`
  - `synthesize_parts(parts, voice, rate=1.0, pitch=0.0)`에 `pitch`를 추가한다. 이 값은 `audioConfig.pitch`로 보낸다.
  - 기존 호출은 그대로 동작해야 한다.
- `channels/tts/cache.py` (새 파일): `CachedTTS(inner, folder, provider)`
  - 결과를 `.cache/tts/{sha256}.mp3`와 `.json`(단어 시각, 끝 시각)으로 저장한다.
  - 키는 `provider · voice · rate · pitch · parts(글자·쉼)`이다.
  - `synthesize_parts`의 형태가 같으므로 어디에든 끼울 수 있다.
  - `.cache/`는 `.gitignore`에 넣는다.
- `channels/video/timeline.py` (새 파일): 데이터 클래스와 JSON 저장·읽기
  - `Timeline(width, height, scenes)`
  - `Scene(number, title, image: Path, music: Path | None, duration, clips, cues)`
    - `clips`: `Clip(audio: Path, start)`, 장면 안 상대 시각
    - `cues`: `Cue(text, color, start, stop)`, 장면 안 상대 시각
  - 전체 시각은 장면 길이를 차례로 더해 구한다(`Timeline.starts()`).
- `channels/video/render.py` (새 파일): `render(timeline, work, out, font) -> Path`
  1. **장면 조각:** 그림 확대(기존 `make_segment`의 zoom), 자막 PNG 겹치기, 줄 음성들을 `adelay`+`amix`로 한 트랙으로 합치기, 앞뒤 0.3초 `fade`(검정)를 적용한다.
     - 파일 이름은 장면 내용 해시(그림 파일 내용, clip 음성, cue, 크기, 길이)이고, 같은 이름의 파일이 있으면 다시 만들지 않는다.
  2. **이어 붙이기:** 기존 `concat`(다시 인코딩 없음)을 쓴다.
  3. **음악 섞기:** 장면별 곡을 이어 깐다.
     - 같은 곡이 이어지는 장면들은 한 구간으로 묶어 곡을 반복 재생하고, 구간 사이는 2초 `acrossfade`로 넘긴다.
     - 음악 기본 볼륨은 -18dB이고, 말소리를 사이드체인으로 `sidechaincompress`해서 말할 때 더 줄인다.
     - 영상은 `-c:v copy`로 둔다.
  4. **자막 파일:** cue를 전체 시각으로 바꿔 `.srt`로 쓴다.
- `channels/video/frames.py`
  - `subtitle_png`, `cover_png`, `card_png`에 `size=(1080, 1920)` 기본 인자를 둔다. 기본값이 그대로라 쇼츠 동작은 바뀌지 않는다.
  - `subtitle_png`에 `color=WHITE` 인자를 추가한다.
- `channels/video/ffmpeg.py`: `segment_args`가 여러 음성 입력, 화면 크기, 어두워졌다 밝아지는 전환을 받도록 넓힌다. 쇼츠 호출 형태는 유지한다.
- `core/notion_store.py`
  - `tables(page_id) -> list[list[list[str]]]`: 페이지의 표들을 글자 칸 목록으로 돌려준다. 머리글 줄도 포함한다. `lexicon()`도 이걸 쓰도록 바꾼다.
  - `approved_drama()`: 렌더할 페이지를 찾는다.
  - `series_of(post)`: 연결된 시리즈 페이지 ID를 찾는다.
  - `mark_rendered(post, link)`: 영상 링크를 적는다. 링크는 선택이다.
- `core/config.py`: `DramaSettings`
  - 출력 `out/drama`, 그림 `assets/longform`, 음악 `assets/music`, 캐시 `.cache/tts`
  - `LINE_MAX=24`, `GAP=0.4`, `SCENE_TAIL=1.0`, `MUSIC_DB=-18`

### 드라마 파이프라인 (`pipelines/ai_drama/`, 새 패키지)
- `bible.py`: 표 칸 목록 → `Bible{이름: Character(voice, pitch, rate, color)}` + 문제 목록
- `script.py`: 블록 + Bible → `Episode(scenes=[DramaScene(number, title, music_tag, lines=[Spoken(speaker, emotion, raw)])])`
  - `attach_folder`: 그림·출처를 붙인다.
  - `script_problems`: 렌더 전 검사를 한다.
- `build.py`: `build_timeline(episode, bible, tts, lexicon, work, settings) -> Timeline`
- `__main__.py`
  - 실행: `python -m pipelines.ai_drama [--dry-run] [--content-id ID]`. `--from-drive`, `--no-upload`는 운영 설계에서 추가한다.
  - `run(store, make_video, log, ..., uploader=None, notifier=None)`: 업로드·알림을 주입받을 자리를 처음부터 둔다. 둘 다 없으면 로컬에만 저장한다.
  - pipelines끼리 import하지 않는다. 쇼츠와 겹치는 코드는 `channels/`, `core/`에만 둔다.

## 3. 흐름

### 시간 계산 (`build.py`)
장면마다 시각 t를 0부터 시작해 줄 단위로 계산한다.
1. 줄을 `narration.to_lines(raw, lexicon, LINE_MAX)`로 자막 줄로 나눈다.
2. 줄 전체 조각을 화자의 목소리·빠르기·높낮이로 `tts.synthesize_parts`에 넘긴다(캐시를 거침).
   - 음성 끝 시각은 `speech.end`이고, 없으면 파일 길이를 쓴다.
   - 줄 끝의 `[쉼]`은 SSML 안에 들어가 길이에 포함된다.
3. `Clip(audio, t)`를 추가한다. `line_cues(...)`의 각 cue에 t를 더하고 화자 색을 붙여 `Cue`로 추가한다.
4. t를 `t + 길이 + GAP`으로 옮긴다.
5. 장면 길이는 `마지막 줄 끝 + SCENE_TAIL`이다.

결과는 `out/drama/{id}.timeline.json`에 저장한다.

### dry-run
- 렌더 전 검사를 하고, 문제가 없으면 TTS까지 돌려(캐시 사용) 장면별·전체 길이를 로그에 남긴다.
  - 예: `장면 3 · 저녁 식탁 1분 12초 (12줄)` / `전체 21분 40초`
- 렌더·업로드·상태 변경은 하지 않는다.

### 실행
1. 채널 `YT-롱폼` + status APPROVED인 페이지를 찾는다(`--content-id`로 하나만 고를 수 있다).
2. 시리즈 바이블, 본문, 발음 사전을 읽고 폴더를 붙인 뒤 검사한다.
3. 타임라인을 만들고 렌더한다.
4. `uploader`가 있으면 `.mp4`와 `.srt`를 올린다(운영 설계).
5. `mark_rendered(post, link)`로 상태를 RENDERED로 바꾸고, 링크가 있으면 `영상 링크`에 적는다.

## 4. 오류 처리

쇼츠와 같은 방식으로 처리한다. 실패하면 `store.mark_failed(post, 사유)`로 status를 FAILED로 바꾸고 `오류`에 사유를 적는다. 다시 렌더하려면 사람이 APPROVED로 되돌린다.

| 실패 | 처리 |
|---|---|
| 렌더 전 검사 | 문제 목록을 `;`로 이어 `오류`에 적는다 |
| TTS (`TTSError`, 네트워크) | `tts: …`. 성공한 줄은 캐시에 남아 다음 실행 때 이어서 진행한다 |
| ffmpeg (`VideoError`) | `render: 장면 N: …` (ffmpeg 출력 끝부분) |
| 글꼴·파일 (`FontError`, `OSError`) | `render: …` |
| 업로드 (uploader가 있을 때) | `upload: …`. 로컬 파일은 남는다. 다시 실행하면 TTS와 장면 조각은 캐시를 쓰므로 음악 섞기와 업로드만 다시 한다 |

키·토큰 값은 오류 메시지와 로그에 넣지 않는다. HTTP 오류는 상태 코드와 응답 본문의 오류 메시지만 남긴다.

## 5. 테스트

TDD로 진행한다. TTS·Notion·Drive는 가짜 객체로 바꾼다.

- **`bible.py`:** 머리글 이름으로 칸 찾기, 빈 칸 기본값, 자동 색 팔레트, `내레이션` 줄 누락·형식 오류
- **`script.py`:**
  - `이름:`, `이름(감정):`, 내레이션 구분
  - 콜론이 있어도 바이블에 없는 긴 문장은 내레이션으로 보기 (예: `시간이 흘러: …`는 공백 때문에 인물 형태가 아님)
  - 바이블에 없는 짧은 이름은 오류
  - 장면 제목·음악 태그·앞 곡 이어 가기
  - 장면 전 대사 오류, 폴더 그림·출처, 음악 파일·출처 검사
- **`tts/cache.py`:** 같은 입력이면 두 번째 호출에서 inner를 부르지 않음. voice·rate·pitch·provider·쉼이 바뀌면 다시 부름
- **`google.py`:** `pitch`가 요청 본문에 들어감. 기본 호출은 기존과 같음
- **`timeline.py`:** JSON 왕복이 같음, `starts()` 누적
- **`build.py`:** 가짜 TTS로 줄 간격(GAP), 장면 길이(SCENE_TAIL), cue 시각·색, 시각 정보가 없을 때 글자 수로 나누기
- **`render.py`:**
  - ffmpeg 인자 생성: adelay·amix, fade, acrossfade, sidechaincompress, 영상 copy
  - 장면 해시가 같으면 다시 만들지 않음, 그림 내용이 바뀌면 다시 만듦
  - `.srt` 전체 시각
  - 실제 ffmpeg로 2초짜리 장면 2개 + 음악 1곡을 렌더해 길이를 확인하는 통합 테스트 1개
- **`frames.py`:** 가로 크기 PNG, 자막 색. 기존 쇼츠 테스트는 그대로 통과
- **`notion_store`:** `tables()`, `lexicon()` 회귀, `series_of`, `mark_rendered` 링크
- **`__main__`:** dry-run은 상태를 바꾸지 않음, 검사 실패 → FAILED, 가짜 uploader 실패 → FAILED `upload:`, uploader 없음 → RENDERED(링크 없음)
- **실제 확인:** Notion에 장면 3개짜리 시험 시리즈·에피소드를 만들어 렌더하고, 프레임을 뽑아 자막 색·한 줄 자막·전환을 확인한다. 음악 줄이기는 직접 들어 본다.

## 나중 작업 (이 설계가 막지 않음)
- 감정 TTS 전환: `CachedTTS(provider=...)`에 새 클라이언트를 끼우고, `Spoken.emotion`을 넘긴다.
- 장면 안 그림 바꾸기 `[그림 03b]`: `Scene`을 그림 구간 목록으로 넓힌다.
- 효과음 `[효과 X]`: `Clip`에 효과음 종류를 추가한다.
- 쇼츠를 `Timeline` + `render`로 옮긴다.
- [5] YouTube 업로드: Drive의 파일을 비공개로 올리고 `containsSyntheticMedia=true`를 설정한다.
- 미디어 폴더를 Drive에서 받기: 운영 설계의 `--from-drive`가 `assets/…`로 받아 오므로 엔진은 로컬 폴더만 안다.
