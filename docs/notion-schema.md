# Notion 스키마

워크스페이스: young님의 워크스페이스 (개인) · 허브 페이지: [moruu 운영](https://app.notion.com/p/4060676ed1e9814198dbdd7c8cb96bbd)

> 속성 이름은 `core/schema.py` 와 같이 바꾼다. 이름을 바꾸면 게시·수집이 멈춘다. 새 속성 추가는 괜찮다.
> `status` 는 Notion **선택(select)** 타입이다 ("상태" 타입으로 바꾸면 API 필터가 400 오류).
> 코드는 `Notion-Version: 2022-06-28` 로 아래 **DB ID** 를 사용한다 (data source ID 아님).

| DB | DB ID (`.env`) | data source |
|---|---|---|
| 콘텐츠 | `d21f8e04b3c0484083441208c4803055` → `NOTION_DB_CONTENT` | `collection://e0d9d00b-080d-4139-8a9f-5ce09d5935a2` |
| 성과 | `cf3660bfccba4e039154da7f906825d2` → `NOTION_DB_METRICS` | `collection://c23a13f8-dd87-4527-b126-7387be2e2a4e` |
| 실패 로그 | `9704e07520644ec2b87ded4c93f15ff0` → `NOTION_DB_FAILURES` | `collection://2d831700-8e5b-4496-b2bc-d2fd6daf2476` |
| 📚 시리즈 | `87c3779468294b11b0956d3564e4d23e` (코드는 콘텐츠의 `시리즈` 연결을 따라감, .env 불필요) | `collection://6f6b055e-44c7-4e60-9a58-122cd717d412` |

## 콘텐츠

| 속성 | 타입 | 옵션 / 비고 |
|---|---|---|
| content_id | title | `TH-주제-YYYYMMDD-001` |
| 채널 | select | Threads, YT-쇼핑, YT-롱폼(시니어 드라마), YT-드라마 |
| 역할 | select | 인지, 브릿지, 수익 |
| status | select | DRAFT, APPROVED, POSTING, POSTED, FAILED, RENDERED(영상 mp4 완성) |
| 예약시각 | date | 비어 있으면 게시 안 됨 |
| 본문 | rich_text | 500자 이하, 링크 직접 넣지 않기 |
| 글자수 | formula | `length(prop("본문"))` (사람용, 코드 미사용) |
| 링크 | url | 첫 댓글로 게시 |
| 대가성문구 | rich_text | 링크가 있으면 필수 |
| 목소리 | select | 여, 남 — 쇼츠 기본 목소리 (비우면 여) |
| 시리즈 | relation | → 📚 시리즈 DB. YT-롱폼 필수 (인물·목소리를 여기서 읽음) |
| 영상 링크 | url | 자동 (렌더 결과 주소, 업로드할 때) |
| 메모 | rich_text | 사람용, 코드 미사용 |
| 게시시각 | date | 자동 |
| 게시ID | rich_text | 자동 |
| 댓글ID | rich_text | 자동 |
| 오류 | rich_text | 자동 (FAILED 사유) |
| 수집_24h / 수집_72h / 수집_7d | checkbox | 자동 |

보기: 기본 표 · 상태 보드(status 그룹) · 예약 캘린더(예약시각) · 🧵 Threads(채널=Threads 표) · 📺 쇼츠(채널=YT-쇼핑, status 보드) · 🎬 롱폼(채널=YT-롱폼, status 보드)

페이지 배치: 제목 아래 `채널`·`status` 고정, 속성은 공통 / Threads 전용 / 자동 기록 구역으로 나누고 빈 칸은 숨김.
허브 하위 페이지: 📺 쇼츠 작업실 · 🎬 롱폼 작업실 (작성 순서 + 대본 견본 + 채널별 status 보드) · 📚 시리즈 DB (견본: 🧪 시험 시리즈).

### YT-쇼핑 페이지 본문 (쇼츠 대본)

`pipelines/shopping_shorts` 가 읽는다. `대가성문구` 필수. 기본 목소리는 `목소리` 속성(여/남, 비우면 여).

```
[이미지 블록, 캡션 = 출처]          ← 선택. 없으면 폴더 파일, 그것도 없으면 크림색 카드
> 가스레인지 모서리 **기름때**       ← 인용 블록 = 상단 화면 문구 (선택, 30자 이하, 굵게 = 노랑)
가스레인지 모서리, 닦기 불편하셨죠?  ← 한 줄 = 자막 한 줄 (14자 넘으면 자동으로 나눔)
                                    ← 빈 줄 = 다음 컷
> 이럴 땐 **얇은 솔**
이럴 땐 {3M|쓰리엠} 같은 솔을 써 보세요. [쉼 0.5] #남 #4초
```
- 컷 나누기: 빈 줄, 또는 대사가 이미 있는 컷 뒤에 오는 이미지·인용 블록. 제목·코드 블록·콜아웃은 무시.
- 줄 끝 태그: `#남`/`#여` 이 컷 목소리, `#4초` 컷 길이 고정 (대사보다 짧으면 FAILED).
- `{글자|읽기}` 자막엔 글자, 소리는 읽기 · `[쉼 0.5]` 0.5초 멈춤.
- 발음 사전: 허브 아래 "발음 사전" 페이지의 표(글자 | 읽기). `.env` `NOTION_PAGE_LEXICON` 에 페이지 ID.
- 폴더 화면: `assets/shorts/{content_id}/01.png` … 번호 = 컷 번호. Notion 이미지가 있는 컷은 Notion 이 먼저.
  출처는 같은 폴더 `출처.txt` — `03: https://…` 처럼 번호별, 번호 없는 줄은 나머지 전체. 영상(.mp4)은 아직 미지원.
- 마무리 카드(프로필 링크 안내 · 모양·크기 확인 · 대가성문구)는 자동으로 붙는다.
- 흐름: DRAFT → (사람) APPROVED → (렌더) RENDERED, 검사·렌더 실패는 FAILED + 오류 칸.

### YT-롱폼 페이지 본문 (시니어 드라마 대본)

`pipelines/ai_drama` 가 읽는다. `시리즈` 연결 필수.

```
## 장면 1 · 저녁 식탁 #음악 잔잔       ← 제목2 = 새 장면. #음악 태그 없으면 앞 장면 곡을 이어 감
그날 저녁, 시어머니는 말없이 상을 차렸다.  ← 문단 한 줄 = 대사 한 줄. 이름이 없으면 내레이션
시어머니(서운하게): 너희 이번 주말에 올 거니?   ← 바이블 인물 "이름:" (괄호 = 감정, 지금은 기록만)
아들: 회사 일이 좀 바빠서요… [쉼 0.5]
```
- 대사 안 문법은 쇼츠와 같다: `{글자|읽기}`, `[쉼 0.5]`, 발음 사전. 24자 넘는 줄은 자막 여러 줄로 자동 나눔.
- 줄 맨 앞이 띄어쓰기 없는 8자 이내 `낱말:` 인데 바이블에 없으면 FAILED (`시간이 흘러: …` 처럼 띄어쓰기가 있으면 내레이션).
- 제목2·문단이 아닌 블록(콜아웃·인용·코드·제목1·3)은 메모로 무시. 첫 장면 제목 전 대사는 FAILED.
- 그림: `assets/longform/{content_id}/01.png` … 번호 = 장면 번호 (.png/.jpg/.jpeg/.webp), 장면마다 필수. 출처는 같은 폴더 `출처.txt` (쇼츠와 같은 형식).
- 음악: `assets/music/{태그}.mp3` (.m4a/.wav). 출처는 `assets/music/출처.txt` 에 `잔잔: YouTube 오디오 보관함` 처럼 (번호 없는 줄 = 기본 출처).
- 결과: `out/drama/{content_id}.mp4` · `.srt` · `.timeline.json`. 흐름은 쇼츠와 같음 (실패 → FAILED + 오류 `tts:`/`render:`/`upload:`).

## 시리즈 (롱폼)

📚 시리즈 DB — 페이지 하나 = 시리즈 하나. 본문의 표(머리글 행 켜기)가 인물 바이블. 칸은 머리글 이름으로 찾는다 (순서 무관).

| 인물 | 목소리 | 높낮이 | 빠르기 | 자막색 | 나이·성격 | 그림 설명 |
|---|---|---|---|---|---|---|
| 내레이션 | ko-KR-Neural2-A | 0 | 0.95 | 흰색 | | |
| 시어머니 | ko-KR-Neural2-A | -4 | 0.9 | 노랑 | 68세, 말수 적음 | 회색 단발 |

- `내레이션` 줄 필수. 목소리 = Google TTS 목소리 이름 (`uv run python -m channels.tts --list-voices`).
- 높낮이: 반음 -20~20 (비우면 0) · 빠르기: 0.25~4.0 (비우면 `.env` TTS_RATE).
- 자막색: 흰색·노랑·하늘·연두·분홍·주황·보라 또는 `#RRGGBB`. 비우면 내레이션 흰색, 인물은 안 쓴 색부터 자동.
- `나이·성격`·`그림 설명` 은 렌더에 안 쓴다 (대본·그림 만들 때 참고).

## 성과

| 속성 | 타입 |
|---|---|
| 기록 | title |
| content_id | rich_text |
| 경과 | select (24h, 72h, 7d) |
| 실제경과h | number |
| 조회 / 좋아요 / 댓글 / 리포스트 / 인용 | number |
| 수집시각 | date |

## 실패 로그

| 속성 | 타입 |
|---|---|
| 요약 | title |
| content_id | rich_text |
| step | select (post, reply, insight, token) |
| error_code | rich_text |
| message | rich_text |
| retry_count | number |
| final_status | select (FAILED, POSTED_NO_REPLY, SKIPPED) |
| time | date |

보기: 기본 표 · 최근 실패(time 내림차순)
