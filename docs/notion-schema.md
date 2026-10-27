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
| 채널 | select | Threads, YT-쇼핑, YT-드라마 |
| 역할 | select | 인지, 브릿지, 수익 |
| status | select | DRAFT, APPROVED, POSTING, POSTED, FAILED |
| 예약시각 | date | 비어 있으면 게시 안 됨 |
| 본문 | rich_text | 500자 이하, 링크 직접 넣지 않기 |
| 글자수 | formula | `length(prop("본문"))` (사람용, 코드 미사용) |
| 링크 | url | 첫 댓글로 게시 |
| 대가성문구 | rich_text | 링크가 있으면 필수 |
| 메모 | rich_text | 사람용, 코드 미사용 |
| 게시시각 | date | 자동 |
| 게시ID | rich_text | 자동 |
| 댓글ID | rich_text | 자동 |
| 오류 | rich_text | 자동 (FAILED 사유) |
| 수집_24h / 수집_72h / 수집_7d | checkbox | 자동 |

보기: 기본 표 · 상태 보드(status 그룹) · 예약 캘린더(예약시각)

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
