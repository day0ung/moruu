# moruu

쇼핑 콘텐츠 부업 자동화 레포. Threads · 쿠팡 파트너스 · YouTube 쇼핑 쇼츠 · (추후) AI 드라마.

- **Notion** = 운영 DB (승인·기록)
- **코드** = 반복 작업 (링크·게시·수집·렌더)
- **사람** = 촬영·승인·리뷰

상세 계획: [docs/PLAN.md](docs/PLAN.md) · 근거 자료: `../gomgom/정리/`

---

## 1. 전체 구조

```mermaid
flowchart LR
    subgraph ME["👤 나 (폰 / PC)"]
        N1["Notion 앱<br/>페이지 생성·승인"]
        D1["Drive 앱<br/>촬영 3컷 업로드"]
        C1["Claude Code<br/>(Notion MCP)<br/>초안·리뷰"]
    end

    subgraph STORE["저장소"]
        NOTION[("Notion DB<br/>콘텐츠·상품·성과<br/>소재은행·실패로그")]
        DRIVE[("Google Drive<br/>moruu-inbox/")]
    end

    subgraph GHA["GitHub Actions (비공개 레포)"]
        JOB["하루 2회 고정<br/>+ 수동 실행 버튼"]
    end

    subgraph OUT["플랫폼"]
        TH["Threads"]
        YT1["YouTube<br/>쇼핑 채널"]
        YT2["YouTube<br/>드라마 채널 (추후)"]
        CP["쿠팡 파트너스"]
    end

    N1 --> NOTION
    C1 <--> NOTION
    D1 --> DRIVE
    JOB <-->|"Notion API"| NOTION
    JOB -->|"서비스 계정"| DRIVE
    JOB --> TH
    JOB --> YT1
    JOB -.-> YT2
    JOB <-->|"딥링크·리포트"| CP
```

> Claude(대화)는 **MCP**, 무인 스케줄러는 **Notion API 토큰** — MCP는 OAuth 대화형이라 cron에서 못 씀.

---

## 2. 레포 구조 (모노레포)

```mermaid
flowchart TB
    ROOT["moruu/"]
    ROOT --> CORE["core/<br/>config · notion_store<br/>safety · logging"]
    ROOT --> CH["channels/<br/>플랫폼 클라이언트"]
    ROOT --> PL["pipelines/<br/>콘텐츠 흐름"]
    ROOT --> APPS["apps/threads-auth-page<br/>(OAuth redirect)"]
    ROOT --> SK[".claude/skills/<br/>레포 전용 스킬"]

    CH --> CHT["threads"]
    CH --> CHY["youtube"]
    CH --> CHC["coupang"]

    PL --> P1["threads-post"]
    PL --> P2["shopping-shorts"]
    PL --> P3["ai-drama (추후)"]

    P1 --> CORE
    P2 --> CORE
    P3 --> CORE
    P1 --> CHT
    P2 --> CHY
    P2 --> CHC
    P3 --> CHY
```

규칙: **pipelines끼리 import 금지** → `core/`, `channels/`만 공유. 채널(계정)·토큰은 쇼핑/드라마 분리.

---

## 3. 콘텐츠 상태 흐름 (Notion `status`)

```mermaid
stateDiagram-v2
    direction LR
    [*] --> 촬영예정: 👤 페이지 생성
    촬영예정 --> 촬영완료: 👤 Drive에 3컷 업로드
    촬영완료 --> 대본대기: 🤖 다운로드·검사 통과
    촬영완료 --> 촬영보완: 🤖 검사 실패
    촬영보완 --> 촬영완료: 👤 다시 업로드
    대본대기 --> DRAFT: 🤖 AI 초안 3개
    DRAFT --> APPROVED: 👤 선택·수정·승인
    APPROVED --> 렌더완료: 🤖 TTS·자막·합성
    렌더완료 --> 업로드_비공개: 🤖 YouTube private
    업로드_비공개 --> POSTED: 👤 폰 확인 후 공개
    APPROVED --> FAILED: 🤖 오류 (재시도 2회 후)
    POSTED --> [*]
```

- 👤 = 사람, 🤖 = 자동
- **APPROVED는 사람만 바꿈.** DRAFT·UNKNOWN 자동 게시 절대 X
- Threads 글은 `DRAFT → APPROVED → POSTED`만 사용 (촬영 단계 없음)

---

## 4. 쇼핑 쇼츠 파이프라인

```mermaid
sequenceDiagram
    autonumber
    actor 나
    participant N as Notion
    participant D as Drive
    participant G as GitHub Actions
    participant A as AI (대본)
    participant Y as YouTube

    나->>N: 콘텐츠 페이지 (상품·상황 메모) / 촬영예정
    G->>D: moruu-inbox/{content_id}/ 생성
    G->>N: 촬영폴더 링크 기록
    나->>D: 1_문제 · 2_사용 · 3_결과 업로드
    나->>N: 촬영완료
    G->>D: 다운로드 → ffprobe 검사
    G->>A: 상품 + 타깃 + 잘된 글 구조
    A-->>N: 대본 초안 3개 + 확인필요 목록 (DRAFT)
    나->>N: 대본 선택·수정 → APPROVED
    G->>G: TTS → SRT 자막 → ffmpeg 9:16 합성
    G->>Y: 비공개 업로드 (설명란 쿠팡 링크 + 대가성 문구)
    나->>Y: 폰에서 확인 → 공개
    G->>N: 24h / 72h / 7d 성과 기록
```

원칙: **제품 장면은 실제 촬영만** · 업로드는 항상 비공개 먼저 · AI 장면 있으면 `containsSyntheticMedia=true`

---

## 5. 실행 일정 (GitHub Actions)

```mermaid
flowchart LR
    T1["⏰ KST 08:00<br/>cron 0 23 * * *"] --> RUN
    T2["⏰ KST 20:00<br/>cron 0 11 * * *"] --> RUN
    BTN["🖱 수동 실행<br/>Actions → Run workflow"] --> RUN
    RUN{{"concurrency: threads<br/>겹쳐 실행 방지"}}
    RUN --> S1["APPROVED & 예약시각 지난 글 게시"]
    RUN --> S2["24h/72h/7d 근접 글 인사이트 수집"]
    RUN --> S3["토큰 만료 임박 시 갱신"]
    S1 & S2 & S3 --> LOG[("Notion 성과 · 실패 로그")]
```

- 예약 실행은 수십 분 늦을 수 있음 (정각 보장 X)
- 사용량: 월 ~100분 수준 (비공개 무료 2,000분)

---

## 6. 구현 순서

```mermaid
flowchart TB
    S0["Step 0 · 레포 세팅<br/>폴더 · .env · CLAUDE.md<br/>Threads 파일 가져오기 · Notion MCP"]
    S1["Step 1 · Notion 스키마 + core/<br/>DB 5개 · notion_store · safety"]
    S2["Step 2 · Threads 반자동<br/>게시 · 첫 댓글 링크 · 인사이트<br/>토큰 갱신 · Actions"]
    GATE1{{"수동 게시 30개<br/>+ 쿠팡 최종 승인"}}
    S25["Step 2.5 · 수익 리포트<br/>Notion 주간·월간 페이지 자동 작성"]
    S3["Step 3 · 쿠팡 API<br/>딥링크 · 일일 리포트"]
    S4["Step 4 · YouTube 쇼핑 쇼츠<br/>Drive 수집 · 대본 · TTS · 렌더 · 비공개 업로드"]
    S5["Step 5 · AI 드라마 (추후)<br/>별도 채널 · 시리즈 바이블 · AI 라벨"]

    S0 --> S1 --> S2 --> GATE1
    GATE1 -->|"자동 게시 ON"| S3
    S2 --> S25 --> S4
    S3 --> S4
    S4 --> S5

    style GATE1 fill:#fff3cd,stroke:#d39e00,color:#000
    style S5 stroke-dasharray: 5 5
```

---

## 7. 레포 로컬 스킬 (`.claude/skills/`)

```mermaid
flowchart LR
    subgraph 우선["우선 만들기"]
        K1["threads-draft"]
        K2["shorts-script"]
        K3["notion-ops"]
        K4["weekly-review"]
    end
    subgraph 다음["다음"]
        K5["coupang-link"]
        K6["youtube-upload"]
    end
    subgraph 추후["추후"]
        K7["drama-bible"]
    end
    우선 --> 다음 --> 추후
```

외부 참고: Remotion 공식 스킬(드라마 단계), faceless-shorts 예제(구조 참고). 자세한 판단은 [PLAN.md §5](docs/PLAN.md).

---

## 8. 결정 현황

| # | 항목 | 상태 |
|---|---|---|
| 1 | 언어 | ✅ Python 3.12 + uv |
| 2 | Notion 플랜 | ✅ Free → 영상은 Drive |
| 3 | 스케줄러 | ✅ GitHub Actions, 하루 2회 + 수동 (KST 08:00 / 20:00) |
| 4 | TTS | ⏳ 나중에 |
| 5 | Threads 폴더 | ✅ 복사 |
| 6 | 수익 리포트 | ✅ Notion 리포트 페이지 (차트는 나중에 Looker) |
