# moruu — 레포 구성 & 구현 계획 (초안)

> 작성 2026-10-27. 근거 문서: `../gomgom/정리/` (08·11·12·13 운영/개발, 02~06·09·부록 참고)
> 상태: **초안 — 승인 전 구현 안 함**

---

## 0. 한 줄 요약

`moruu` 하나의 **모노레포**에 Threads · 쿠팡 · YouTube 쇼츠 · (추후) AI 드라마를 모듈로 나눠 넣고,
**Notion = 운영 DB(승인·기록)**, **코드 = 반복 작업(링크·게시·수집)**, **사람 = 승인·리뷰**로 역할을 나눈다.

---

## 1. 현재 가진 것

| 위치 | 내용 | 처리 |
|---|---|---|
| `../gomgom/threads-auto/get_token.ps1` | 인증 코드 → 단기 → **장기 토큰** 교환, `.env`에 USER_ID·TOKEN·발급일 저장 | `channels/threads/scripts/`로 이동 |
| `../gomgom/threads-auto/.env` | `THREADS_APP_ID`, `THREADS_APP_SECRET`, `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `THREADS_TOKEN_ISSUED` | 루트 `.env`로 **복사만** (git 제외, 내용은 커밋/로그 금지) |
| `../gomgom/threads-auth-page/index.html` | OAuth redirect 페이지 (`threads-auth.netlify.app`), 코드 표시만 | `apps/threads-auth-page/`로 이동 (Netlify 배포 경로 유지) |
| `moruu/` | 빈 git 레포 | 여기서 작업 |

부족한 것: 토큰 **갱신** 스크립트 (장기 토큰 60일 → `th_refresh_token`으로 만료 전 갱신), 게시/수집 코드 전부.

---

## 2. 레포 관리 — 모노레포 추천

### 왜 모노레포인가
- 1인 운영. 레포를 나누면 `.env`·Notion 클라이언트·로깅·안전 규칙을 매번 복붙하게 됨
- 공통 부품(Notion 저장소, 대가성 문구 체크, 중복 키, 업로드 클라이언트)을 쇼핑 쇼츠와 AI 드라마가 같이 씀
- 나중에 AI 드라마가 커지면 그때 `pipelines/ai-drama`만 떼어내면 됨

### 분리 원칙 (자료 원칙 반영)
- **채널(계정)은 분리, 코드는 공유.** 쇼핑 채널과 드라마 채널은 YouTube 채널/토큰을 따로 (`YOUTUBE_SHOP_*`, `YOUTUBE_DRAMA_*`) — "시청 이유가 다르면 채널 약속도 분리" (GG-쇼츠심화 P1)
- 파이프라인끼리 직접 import 금지 → `core/`와 `channels/`만 공유

### 폴더 구조
```
moruu/
├─ CLAUDE.md                  # 레포 규칙 (안전 규칙·금지사항·폴더 설명) — Claude가 매번 읽음
├─ .mcp.json                  # Notion MCP (project scope)
├─ .env / .env.example        # .env는 gitignore
├─ pyproject.toml             # uv 워크스페이스
├─ docs/
│  ├─ PLAN.md                 # 이 문서
│  └─ notion-schema.md        # Notion DB 속성 정의
├─ apps/
│  └─ threads-auth-page/      # 기존 OAuth redirect 페이지
├─ core/                      # 공통: config, notion_store, safety(문구·중복·상한), logging(키 마스킹)
├─ channels/                  # 플랫폼 클라이언트 (얇게, 게시/조회만)
│  ├─ threads/                #   container→publish→reply, insights, 한도, 토큰 갱신
│  │  └─ scripts/get_token.ps1
│  ├─ youtube/                #   OAuth, videos.insert(비공개 업로드), 메타데이터, 통계
│  └─ coupang/                #   HMAC 서명, 딥링크, 검색, 리포트 (최종 승인 후)
├─ pipelines/                 # 콘텐츠 만드는 흐름
│  ├─ threads-post/           #   Notion APPROVED → 게시 → 24h/72h/7d 수집
│  ├─ shopping-shorts/        #   대본 → TTS → 자막 → 렌더(ffmpeg) → 업로드
│  └─ ai-drama/               #   (추후) 시리즈 바이블 → 에피소드 → 장면 생성 → 합성
├─ assets/                    # 직접 찍은 클립, BGM (대용량은 gitignore, 경로만 Notion에)
├─ .claude/skills/            # 레포 전용 스킬 (§5)
└─ logs/                      # 토큰·키 절대 기록 안 함
```

### 언어: Python 3.12 + `uv` (추천)
- Threads/YouTube/Notion/쿠팡 모두 HTTP라 언어 상관없음. YouTube 공식 `google-api-python-client`, `notion-client`, 영상은 `ffmpeg` 호출이면 충분
- Remotion(React 영상)은 **AI 드라마에서 자막 애니메이션 등이 필요할 때** 별도 `pipelines/ai-drama/render/`(Node)로 추가 검토
- 기존 `get_token.ps1`은 그대로 두고, 갱신 로직만 Python으로

> ⚠ 결정 필요: Python으로 갈지, TypeScript(Node)로 통일할지. Remotion을 초반부터 쓸 거면 Node 통일이 낫다.

---

## 3. Notion 관리 방식

### 핵심: MCP와 API를 둘 다 쓴다
| 누가 | 무엇으로 | 하는 일 |
|---|---|---|
| **나 + Claude (대화)** | **Notion MCP** (`https://mcp.notion.com/mcp`, OAuth) | 초안 검토, APPROVED 처리, 주간 리뷰, 소재 은행 정리, "이번 주 상위 글 뽑아줘" |
| **스케줄러 (무인)** | **Notion API** (Internal Integration 토큰, `NOTION_TOKEN`) | APPROVED 읽기, POSTED·성과 쓰기, 실패 로그 |

→ MCP는 OAuth 대화형이라 cron에서 못 씀. **무인 실행 코드는 공식 API**, 사람 작업은 MCP.

### 설정
```bash
claude mcp add --transport http --scope project notion https://mcp.notion.com/mcp
# Claude Code에서 /mcp → OAuth 완료
```
`--scope project` → `.mcp.json`에 저장되어 이 레포에서만 사용.
제약: 워크스페이스 멤버만 연결 가능. SQL 쿼리 무제한·커넥터 검색은 Business/Enterprise + Notion AI 필요 (일반 플랜은 저장된 view 조회 위주).

### DB 구성 (13번 데이터 구조를 Notion으로)
| DB | 주요 속성 | 관계 |
|---|---|---|
| **콘텐츠** | content_id(`TH-LIVING-20261101-001`, `YS-…`, `DR-…`), 채널(Threads/YT-쇼핑/YT-드라마), 역할(인지/브릿지/수익), 훅유형, 본문/대본, **status**(DRAFT→APPROVED→POSTED/FAILED), 예약시각, 게시ID, 대가성문구 ✔, AI라벨 ✔ | → 상품, 성과 |
| **상품** | 상품명, 쿠팡URL, 파트너스링크, 가격대, 로켓, 25점표 점수, 품절/가격변동 체크일 | ← 콘텐츠 |
| **성과** | content_id, 경과(24h/72h/7d), 조회·좋아요·댓글·클릭·주문·수익 | ← 콘텐츠 |
| **소재 은행** | 문제, 타깃, 출처(구조만), 구매질문 여부 | → 콘텐츠 |
| **실패 로그** | time, content_id, step, error_code, message, retry, final | |
| (추후) **드라마 시리즈** | 시리즈 바이블, 캐릭터 시트, 에피소드 목록 | → 콘텐츠 |

**규칙:** 코드는 `status=APPROVED`만 처리. DRAFT/UNKNOWN 자동 게시 절대 금지. APPROVED는 사람만 바꿈.

---

## 4. 구현 단계

> 13번 문서의 Phase 순서를 그대로 따르고 YouTube를 뒤에 붙임. 각 단계 끝에 "완료 기준" 확인 후 다음으로.

### Step 0 — 레포 세팅 (0.5일)
- [ ] 폴더 구조, `pyproject.toml`, `.gitignore`(`.env`, `assets/raw`, `logs/`, `.idea/`)
- [ ] 기존 Threads 파일 이동 (`.env`는 복사만, 원본은 그대로)
- [ ] `CLAUDE.md` — 안전 규칙 표(13번) + 금지사항(12번 STEP 7) 넣기
- [ ] Notion MCP 연결, Notion API Integration 생성 → 각 DB에 연결

### Step 1 — Notion 스키마 + `core/` (1일)
- [ ] Notion DB 5개 생성 (MCP로 Claude가 생성), `docs/notion-schema.md`에 ID·속성 기록
- [ ] `core/notion_store`: APPROVED 조회 / status 변경 / 성과 append / 실패 로그
- [ ] `core/safety`: 대가성 문구 없으면 차단, 중복 키, 하루 상한, 수익 글 연속 금지

### Step 2 — Threads 반자동 (13번 Phase 1) (2~3일)
- [ ] `channels/threads`: 컨테이너 생성 → 게시 → 첫 댓글(링크+문구), `threads_publishing_limit` 확인
- [ ] 토큰 갱신 (`th_refresh_token`, 만료 7일 전) + 실패 시 즉시 중단·알림
- [ ] `pipelines/threads-post`: 15분마다 APPROVED & 예약시각 지난 글 게시
- [ ] 수집기: 24h/72h/7d 인사이트 → Notion 성과
- [ ] 실행: **GitHub Actions** (비공개 레포) — 처음엔 PC에서 수동 실행으로 테스트 후 이전
  - 고정 하루 2회 (cron은 UTC 기준) + 아무 때나 수동 실행 버튼(`workflow_dispatch`)
  - 인사이트는 "24h/72h/7d에 가장 가까운 실행"에서 수집하고 실제 경과 시간도 같이 기록
  - Threads 토큰 갱신 → fine-grained PAT(Secrets 쓰기)로 Secret 덮어쓰기
```yaml
# .github/workflows/threads.yml
on:
  schedule:
    - cron: "0 23 * * *"   # KST 08:00
    - cron: "0 11 * * *"   # KST 20:00
  workflow_dispatch:        # Actions 탭 → Run workflow
concurrency: threads        # 겹쳐 실행 방지 (수동+예약 동시 → 중복 게시 막기)
```

완료 기준: Notion에서 APPROVED로 바꾸면 예약 시간에 게시되고 성과가 자동으로 채워짐

> ⚠ 운영 전제 (08·13번): 수동 게시 30개 + 쿠팡 최종 승인이 먼저. 코드는 병행 개발해도 되지만 **자동 게시는 수동 30개 후** 켜기.

### Step 2.5 — 수익 리포트 (Notion) (1~2일)
- [ ] 비용·작업시간·정산·쿠팡 주간 수동 입력용 Notion 템플릿
- [ ] `core/report`: 일별 지표 → 주간/월간 집계 (중앙값·배수·퍼널·병목 판정)
- [ ] 리포트 페이지 자동 작성 (§9-4)

### Step 3 — 쿠팡 파트너스 API (13번 Phase 2) — 최종 승인 후
- [ ] Access/Secret Key 발급, **공식 API 가이드로 인증 방식 재확인** (HMAC 내용은 미검증 정보)
- [ ] 딥링크 생성 → 상품 DB `파트너스링크` 자동 채움 (subId에 content_id)
- [ ] 일일 리포트 → 성과 DB

### Step 4 — YouTube 쇼핑 쇼츠 (반자동)
흐름:
```
[사람] 폰 Notion 앱에서 콘텐츠 페이지 생성 (상품 연결, 상황 한 줄 메모) → status=촬영예정
[자동] Drive에 `moruu-inbox/{content_id}/` 폴더 생성 → Notion `촬영폴더` 속성에 링크 기록
[사람] Notion에서 링크 탭 → Drive 앱에서 영상 3개 업로드 (`1_문제`, `2_사용`, `3_결과`) → status=촬영완료
[자동] 수집기(15분마다): 촬영완료 페이지 → Drive API로 다운로드 → assets/raw/{content_id}/
       → ffprobe 검사(세로·길이·해상도·파일 3개) → 통과 시 status=대본대기 / 실패 시 사유 기록 + status=촬영보완
[AI]   대본 초안 3개 (상황→반응→이유→제품→증명→조건→CTA, 03번 규칙)
[사람] 대본 선택·수정 → APPROVED
[자동] TTS(Typecast 등) → SRT 자막(11~14자, 최대 2줄) → ffmpeg 합성(9:16, BGM -28~-24dB)
[자동] YouTube 업로드 = **비공개(private)** + 설명란 쿠팡 링크 + 대가성 문구
[사람] 폰에서 확인 → 공개 전환 (또는 publishAt 예약)
[자동] 24h/72h/7d 통계 → 성과 DB
```
- [ ] `channels/youtube`: Google Cloud 프로젝트, OAuth(데스크톱 앱), `videos.insert` 비공개 업로드
- [ ] `pipelines/shopping-shorts`: 대본 → TTS → 자막 → 렌더 → 업로드
- [ ] 쿼터: 업로드 1건 ≈ **100 units** (2025-12 변경, 기본 10,000/일). 2026-06부터 `videos.insert`는 별도 쿼터 버킷 → Cloud Console에서 실제 한도 확인
- [ ] 유튜브 쇼핑 제휴(쿠팡 연동 쇼핑태그) 사용 가능 여부는 **채널 조건 확인 후** (11번 문서: 2달차 이후)

**촬영 컷 받기 — Google Drive (Notion Free 플랜이라 파일당 5MB 제한 → 영상은 Drive로)**
- Notion = 상태·메모·링크만, 영상 파일 = Drive. 원본은 로컬 `assets/raw/`(gitignore)에도 보관
- Drive 접근은 **서비스 계정** 추천: `moruu-inbox` 폴더를 서비스 계정 이메일에 공유 → 키 파일로 접근, 토큰 만료 없음, 그 폴더만 보임
- YouTube 업로드는 서비스 계정 불가 → 내 계정 OAuth. 같은 Google Cloud 프로젝트 사용
  - ⚠ OAuth 동의 화면이 **"테스트" 상태면 refresh token이 7일 후 만료** → "프로덕션"으로 게시 (개인용은 미인증 경고만 뜨고 사용 가능)
- 무료 Drive 15GB (Gmail·사진 공유) → 업로드 끝난 콘텐츠의 inbox 폴더는 30일 후 정리
- status 흐름: 촬영예정 → 촬영완료 → 대본대기 → DRAFT → APPROVED → 렌더완료 → 업로드(비공개) → POSTED (실패 시 촬영보완 / FAILED)

**원칙:** 제품 등장·작동 장면은 **실제 촬영만**. 업로드는 항상 비공개로 먼저 → 사람이 공개.

### Step 5 — AI 드라마 (추후, 별도 채널)
- [ ] 별도 YouTube 채널 + 별도 토큰
- [ ] `pipelines/ai-drama`: 시리즈 바이블(인물·세계관) → 에피소드 대본(썰 구조: 고백→맥락→발견→반전→결론) → 장면 프롬프트 → 이미지/영상 생성 → TTS → 합성
- [ ] 업로드 시 **`status.containsSyntheticMedia = true`** (사실적 AI 콘텐츠 표시)
- [ ] 영상 생성 도구(Veo/Kling/Runway 등)는 **상업 이용 약관·요금 비교 후** 결정 — 자료에 없는 영역
- [ ] YPP "반복적·대량생산 콘텐츠" 정책 확인 — 템플릿 찍어내기식은 수익화 거절 위험
- [ ] 쇼핑 하이브리드(이야기=AI, 제품=실사)는 쇼핑 채널에서만, AI 제품 장면 금지

---

## 5. 레포 로컬 스킬 (`.claude/skills/`)

### 직접 만들 스킬 (우선순위 순)
| 스킬 | 언제 | 내용 | 근거 문서 |
|---|---|---|---|
| `threads-draft` | 스레드 글 쓸 때 | 잘된 글 5개 구조 분석 → 초안 3개 → 과장·금지어 체크 → Notion DRAFT 저장 | 03, 04, 부록 프롬프트 |
| `shorts-script` | 쇼츠 대본 | 첫 장면 3안(문제/행동/결과), 7단계 대본, 자막 길이, "확인 필요 주장" 목록 | 03, 04-A, 10 |
| `notion-ops` | Notion 작업 | DB ID·속성 이름·status 규칙, "APPROVED는 사람만" | docs/notion-schema.md |
| `weekly-review` | 주 1회 | 성과 DB → 상위/하위 비교, 막힌 퍼널 단계 1개, 다음 주 실험 1개 | 06, 08 |
| `coupang-link` | 링크 만들 때 | 상품 체크(25점표), 딥링크, 대가성 문구 | 11, 12 |
| `youtube-upload` | 업로드 | 비공개 업로드, 메타데이터, AI 라벨, 쿼터 확인 | Step 4 |
| `drama-bible` (추후) | 드라마 | 시리즈 바이블·캐릭터 일관성·에피소드 템플릿 | 09 |

만들 때는 `anthropic-skills:skill-creator` 사용 (테스트 입력으로 검증까지).

### 가져다 쓸 만한 외부 스킬 (검토 결과)
| 이름 | 용도 | 판단 |
|---|---|---|
| [remotion-dev/skills `remotion-best-practices`](https://remotion.dev/docs/ai/claude-code-plugin) | Remotion 영상 코드 | 공식. **Remotion 쓸 때만** 설치 (AI 드라마 단계) |
| [hassancs91 `claude-faceless-shorts-creator`](https://learnwithhasan.com/guide/how-to-make-faceless-youtube-shorts-with-claude-code/) | 얼굴 없는 쇼츠 파이프라인 (MIT), `.claude/skills/` 구조 + 업로드 전 검증 단계 | **구조 참고용으로 가장 유용.** 그대로 쓰지 말고 파이프라인 설계만 참고 |
| [AgriciDaniel `claude-youtube`](https://awesome.ecosyste.ms/projects/github.com%2Fagricidaniel%2Fclaude-youtube) | 쇼츠 메타데이터·최적화 (베타, 업로드 X) | 제목·설명 템플릿 참고 정도 |
| [Upload-Post skill](https://www.upload-post.com/skills/claude-code/youtube) | 터미널에서 YouTube 업로드 | 유료 외부 서비스 경유 → **비추천.** 공식 YouTube API로 직접 |
| openclaw/skills `youtube-shorts-automation` | Deevid AI 영상 생성 + 자동 업로드 | 완전 자동·외부 AI 의존 → 우리 원칙(사람 승인)과 안 맞음. 비추천 |

> 외부 스킬은 설치 전에 코드·라이선스 직접 확인 (특히 업로드·토큰 다루는 것).

---

## 6. Paperclip 검토 ([day0ung/paperclip](https://github.com/day0ung/paperclip) ← fork of `paperclipai/paperclip`)

**정체:** AI 에이전트 팀을 "회사"처럼 돌리는 오픈소스 컨트롤 플레인 (Node.js 서버 + React UI, MIT). 조직도·예산·승인 게이트·감사 로그·스케줄 루틴·Skills Store, Claude Code/Codex 등 여러 에이전트 어댑터 지원. `npx paperclipai@latest onboard --yes`로 실행, `localhost:3100`.

**ROADMAP 요점:**
- ✅ 플러그인, Skills Manager/Studio/Store, 스케줄 루틴, 예산 하드스톱, 리뷰·승인 게이트, MCP 게이트웨이, 시크릿 매니저, 활동 로그, 샌드박스 실행
- 🟡 메모리/지식(Mem0·Zep 등 실험), Agent Chat, 클라우드 배포
- ⚪ MAXIMIZER MODE(고자율), 작업 큐, 자기조직화, 조직 학습, 데스크톱 앱, Jira/Linear 연동

**moruu에 쓸까?** → **지금은 안 씀. 나중에 검토.**
| | 판단 |
|---|---|
| 지금 | 1인 + 파이프라인 3개 수준. Notion(승인) + 스케줄러 + Claude Code 스킬로 충분. Paperclip은 서버·DB를 하나 더 운영해야 함 |
| 가져올 아이디어 | **승인 게이트**(=Notion APPROVED), **예산 하드스톱**(AI 생성 API 월 비용 상한), **활동 로그**(실패 로그 DB) → 우리 설계에 이미 반영 |
| 결정 (2026-10-27) | 개발은 **Notion 개발 보드 + Claude Code 서브에이전트**로 진행. 이슈·선행작업·승인 구조는 Paperclip과 같게 만들어 두고, Step 4~5에서 Paperclip으로 이전 검토 |
| 재검토 시점 | AI 드라마까지 붙어서 "대본 에이전트 / 렌더 에이전트 / 리뷰 에이전트"를 상시로 돌리고, 영상 생성 비용을 에이전트별로 묶어야 할 때 |

---

## 7. 안전 규칙 (코드 + CLAUDE.md에 고정)

13번 문서 표 그대로 + YouTube 추가:
- APPROVED만 게시 / 대가성 문구 없으면 중단 / 중복 키 / 하루 상한(API 한도보다 훨씬 낮게) / 수익 글 연속 금지
- 재시도 최대 2회, 토큰 만료 시 즉시 중단 + 알림
- 키·토큰은 `.env`만, 로그 마스킹
- **YouTube: 항상 private 업로드 → 사람이 공개. AI 생성 장면 있으면 `containsSyntheticMedia=true`**
- 게시 시간 랜덤 위장 등 탐지 회피 설계 안 함
- AI 영상 생성 API 월 예산 상한 (초과 시 중단)

---

## 8. 결정 (2026-10-27 확정)

1. ~~언어~~ → **Python 3.12 + uv 확정**
2. ~~Notion 플랜~~ → **Free 확정.** 영상은 Drive로(§Step 4). MCP 집계(SQL)는 제한적이라 주간 리뷰 집계는 코드(API)로 계산 후 Notion에 기록
3. ~~스케줄러~~ → **GitHub Actions 확정.** 하루 2회 고정 + 수동 실행. 시간대(기본안 KST 08:00 / 20:00) 확인 필요
   - 고정 시간 **KST 08:00 / 20:00 확정**
4. TTS → **Step 4에서 결정** (Typecast 등, 상업 이용 조건 확인)
5. ~~기존 Threads 폴더~~ → **복사 확정** (원본·Netlify 배포 그대로 유지)

---

## 9. 확장: 수익 리포트 & 지표 (초안)

### 9-1. 보여줄 지표 (06번 분석 노트 기준)
| 묶음 | 지표 | 계산 | 출처 |
|---|---|---|---|
| **돈 (월)** | 확정 수수료 / 지급예정액 / 실제 입금 / 비용 / **순수익** | 순수익 = 입금 + 협찬 − (샘플·도구·AI·제작비) | 쿠팡 정산, 비용 DB |
| | 시간당 순기여액 | 순수익 ÷ 작업시간 | 작업시간 기록 |
| **퍼널 (주)** | 조회 → 클릭 → 주문 → 확정 | 클릭률 = 클릭÷조회, 확정률 = 확정주문÷클릭 | Threads·YouTube·쿠팡 |
| | 막힌 단계 | 진단표(06 §5) 자동 판정: "이번 주 병목 = 클릭" | 계산 |
| **콘텐츠** | 기준선(최근 30개 **중앙값**), 아웃라이어 배수, 상위/하위 5 | 배수 = 조회 ÷ 중앙값 | 성과 DB |
| | 콘텐츠·상품별 수익 TOP | subId(content_id) 단위 | 쿠팡 (subId 지원 시) |
| **채널** | Threads vs YT-쇼핑 비교 | 채널별 퍼널 | 전부 |
| **운영** | 발행량, 실패 건수, API 비용 | | 콘텐츠·실패 로그 |
| **목표** | 최종 승인 진척 (누적 판매 ÷ 15만 원, 블로그 정보 — 공식 확인) | | 쿠팡 |

평균 말고 **중앙값**, 조회 말고 **확정 수수료·순수익**이 메인 숫자.

### 9-2. 데이터 수집 경로
```
Threads 인사이트 ──┐
YouTube Analytics ─┼─→ [GitHub Actions 하루 2회] → 일별 지표(fact) → 주간/월간 집계 → 대시보드
쿠팡 리포트 ───────┘                                    ↑
비용·작업시간 (사람이 Notion에 입력) ────────────────────┘
```
| 소스 | 최종 승인 전 | 최종 승인 후 |
|---|---|---|
| 쿠팡 클릭·주문·수수료 | 파트너스 리포트 화면 → **주 1회 수동 입력** (또는 엑셀 다운로드 기능 있으면 CSV 업로드 → 파싱) | 리포트 API 자동 (일 1회) |
| 쿠팡 정산·입금 | 월 1회 수동 입력 | 정산 화면 확인 후 수동 (입금액은 계좌 기준이라 항상 사람) |
| YouTube | Analytics API (`yt-analytics.readonly` 스코프 추가) | 동일 |
| Threads | 인사이트 API | 동일 |

### 9-3. Notion DB 추가 (Step 1 스키마에 포함)
- **일별 지표**: 날짜, 채널, content_id, 조회, 클릭, 주문, 취소, 수수료(예상/확정), 출처, 수집시각
- **정산**: 정산월, 확정 수수료, 지급예정액, 지급예정일, 실제 입금일·액, 차액 메모
- **비용**: 날짜, 항목(샘플/도구/AI API/기타), 금액, 관련 content_id
- **작업시간**: 날짜, 작업(소싱/촬영/편집/검수), 분

### 9-4. 대시보드 표시 방법 — ✅ Notion 리포트 페이지로 시작
- Actions가 **주간(월요일 08:00 실행분)·월간(1일)** 리포트 페이지를 Notion `리포트` DB에 자동 작성
  - 요약 숫자(순수익·확정 수수료·지급예정), 퍼널 표(이번 주 vs 지난 주), 병목 판정 1줄, 기준선(중앙값)·상위/하위 3, 채널 비교, 최종 승인 진척
  - 집계는 **코드에서 계산** (Free 플랜 MCP 집계 제한 회피), Notion엔 결과만 기록
- 주간 리뷰는 이 페이지를 보고 Claude(`weekly-review` 스킬)와 다음 주 실험 1개 결정
- 나중에 차트가 필요해지면 → 같은 집계 결과를 Google Sheets에도 써서 Looker Studio 연결 (코드 변경은 출력 대상 추가뿐)
- 구현 시점: Step 2(Threads) 수집기 완성 직후 → Step 2.5로 진행

---

## 참고 링크
- Paperclip ROADMAP: https://github.com/day0ung/paperclip/blob/master/ROADMAP.md
- Notion MCP (Claude Code): https://developers.notion.com/guides/mcp/get-started-with-mcp
- YouTube Data API 변경 이력 (업로드 쿼터·containsSyntheticMedia): https://developers.google.com/youtube/v3/revision_history
- Threads API: https://developers.facebook.com/docs/threads/overview
- Remotion Claude Code 플러그인: https://remotion.dev/docs/ai/claude-code-plugin
- Faceless shorts 예제: https://learnwithhasan.com/guide/how-to-make-faceless-youtube-shorts-with-claude-code/
- claude-youtube: https://awesome.ecosyste.ms/projects/github.com%2Fagricidaniel%2Fclaude-youtube
- Upload-Post skill: https://www.upload-post.com/skills/claude-code/youtube
