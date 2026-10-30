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

## 콘텐츠

| 속성 | 타입 | 옵션 / 비고 |
|---|---|---|
| content_id | title | `TH-주제-YYYYMMDD-001` |
| 채널 | select | Threads, YT-쇼핑, YT-롱폼(렌더 설계 중), YT-드라마 |
| 역할 | select | 인지, 브릿지, 수익 |
| status | select | DRAFT, APPROVED, POSTING, POSTED, FAILED, RENDERED(쇼츠 mp4 완성) |
| 예약시각 | date | 비어 있으면 게시 안 됨 |
| 본문 | rich_text | 500자 이하, 링크 직접 넣지 않기 |
| 글자수 | formula | `length(prop("본문"))` (사람용, 코드 미사용) |
| 링크 | url | 첫 댓글로 게시 |
| 대가성문구 | rich_text | 링크가 있으면 필수 |
| 목소리 | select | 여, 남 — 영상 기본 목소리 (비우면 여) |
| 메모 | rich_text | 사람용, 코드 미사용 |
| 게시시각 | date | 자동 |
| 게시ID | rich_text | 자동 |
| 댓글ID | rich_text | 자동 |
| 오류 | rich_text | 자동 (FAILED 사유) |
| 수집_24h / 수집_72h / 수집_7d | checkbox | 자동 |

보기: 기본 표 · 상태 보드(status 그룹) · 예약 캘린더(예약시각) · 🧵 Threads(채널=Threads 표) · 📺 쇼츠(채널=YT-쇼핑, status 보드) · 🎬 롱폼(채널=YT-롱폼, status 보드)

페이지 배치: 제목 아래 `채널`·`status` 고정, 속성은 공통 / Threads 전용 / 자동 기록 구역으로 나누고 빈 칸은 숨김.
허브 하위 페이지: 📺 쇼츠 작업실 · 🎬 롱폼 작업실 (작성 순서 + 대본 견본 + 채널별 status 보드).

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
