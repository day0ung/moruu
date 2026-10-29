
## 1. GitHub 비공개 레포 + push

- [x] github.com/new → 이름 `moruu` 생성 (계정 `day0ung`) — 완료
- [x] push 완료 (main, feat/threads-semi-auto) — 2026-10-27
```bash
git push -u origin main
git push -u origin feat/threads-semi-auto
```
- [ ] GitHub에서 PR 만들어 main 에 병합 (예약 실행은 main 의 워크플로만 동작)
- [ ] 커밋 작성자가 `day0ung` 계정으로 보이는지 확인 → 맞으면 백업 브랜치 삭제: `git branch -D backup/before-author-rewrite`

## 2. Notion Integration (봇 토큰)

- [x] https://www.notion.so/profile/integrations → 새 API 통합 → 이름 `moruu-bot`, 워크스페이스 "young님의 워크스페이스"
- [x] 기능: 콘텐츠 **읽기·업데이트·삽입** → 저장 → 내부 통합 시크릿 복사
- [x] Notion **moruu 운영** 페이지 → `···` → 연결 → `moruu-bot` 추가 (하위 DB 전부 적용)
- [x] `.env` 에 직접 입력 (완료 — 시크릿이 채팅에 노출됐으므로 시험 후 재발급 권장):
```
NOTION_TOKEN=<복사한 시크릿>
NOTION_DB_CONTENT=d21f8e04b3c0484083441208c4803055
NOTION_DB_METRICS=cf3660bfccba4e039154da7f906825d2
NOTION_DB_FAILURES=9704e07520644ec2b87ded4c93f15ff0
MORUU_DAILY_CAP=3
```
- [x] 연결 확인 (값은 출력 안 됨):
```bash
uv run python -c "from dotenv import load_dotenv; import os; load_dotenv(); from core.config import Settings; Settings.from_env(os.environ); print('ok')"
```

## 3. 첫 게시 시험 (로컬)

- [x] Notion 콘텐츠 DB의 예시 글(`TH-LIVING-20261101-001`)에서 `예약시각` = 지금, `status` = **APPROVED**
- [x] `uv run python -m pipelines.threads_post --dry-run` → `[dry-run] 게시 예정: TH-LIVING-20261101-001`
- [x] `uv run python -m pipelines.threads_post --only publish` (2026-10-27 16:27 첫 게시 성공) → Threads 앱에 글 확인, Notion status=POSTED·게시ID 채워짐
- [x] 링크 글 1개 시험 (2026-10-28 우산꽂이 TH-LIVING-20261031-003): `링크` + `대가성문구` 채우고 같은 순서로 → 첫 댓글에 링크+문구 확인
- [ ] 시험 글 삭제 여부 결정

## 4. Threads 토큰 재발급이 필요할 때 (만료·새 PC)

- [ ] Threads 권한 허용 → threads-auth-page(https://threads-auth.netlify.app/)에서 코드 복사
- [ ] `uv run python -m channels.threads.get_token` → 코드 붙여넣기 → `성공: @계정 / 유효기간 N일`

## 5. GitHub Actions Secrets

- [ ] 로컬 `.env` 에서 바로 등록 (gh CLI 로그인 필요: `gh auth login`):
```bash
for k in THREADS_USER_ID THREADS_ACCESS_TOKEN THREADS_TOKEN_ISSUED NOTION_TOKEN NOTION_DB_CONTENT NOTION_DB_METRICS NOTION_DB_FAILURES; do
  grep "^$k=" .env | cut -d= -f2- | tr -d '\r' | gh secret set "$k"
done
```
- [ ] 토큰 갱신용 PAT: GitHub → Settings → Developer settings → Fine-grained tokens → 저장소 `moruu` 만, 권한 **Secrets: Read and write**, 만료 1년 → `gh secret set GH_PAT` → **만료일 캘린더에 기록**
- [ ] Actions → threads → Run workflow → `dry_run` 체크 → 초록불 + 로그에 토큰 없음 확인
- [ ] `dry_run` 해제하고 한 번 더

## 6. 결정할 것

- [ ] **대가성 문구 위치**: 수익 글 본문 맨 앞에도 고지를 넣을지 (공정위 추천·보증 심사지침 확인) — 수익 글 자동 게시 전까지
- [ ] 쿠팡 파트너스 공식 대가성 문구 확인 → Notion 허브 페이지에 기록
- [ ] 운영 전제: **수동 게시 30개 전에는 APPROVED 를 쓰지 않음** (자동 게시 실질적 OFF)

## 6-1. 쿠팡 파트너스 가입

- [x] 개인으로 가입 → 사이트 등록에 **Threads 프로필 주소** (YouTube 는 만든 뒤 추가 등록) — 자세히: [youtube-shorts-coupang.md](youtube-shorts-coupang.md)

## 6-2. Google Cloud TTS 키 (쇼츠 음성)

- [ ] https://console.cloud.google.com → 새 프로젝트 `moruu`
- [ ] 결제 계정 연결 (카드 등록 — 무료 한도 안이면 0원) → **예산 및 알림**에 소액 예산(예: 1,000원) 알림 설정
- [ ] API 및 서비스 → 라이브러리 → **Cloud Text-to-Speech API** 사용 설정
- [ ] 사용자 인증 정보 → API 키 만들기 → **키 제한: API 제한 = Cloud Text-to-Speech API 만**
- [ ] `.env` 에 `GOOGLE_TTS_API_KEY=` 직접 입력 (Mac 의 `.env` 에도) — 채팅에 붙여넣지 말 것
- [ ] 확인: `uv run python -m channels.tts --list-voices`

## 6-3. YouTube 쇼핑 채널 개설

> 1차(로컬 mp4 제작)에는 필요 없음 — 샘플 영상을 보고 올릴 만하다고 판단되면 진행. 메뉴 이름은 바뀔 수 있으니 화면 기준으로.

**채널 만들기**
- [ ] Google Cloud TTS 프로젝트(6-2)와 **같은 Google 계정**으로 로그인 (나중에 업로드 API 연결이 쉬움)
- [ ] YouTube → 프로필 → 설정 → **채널 추가 또는 관리** → 채널 만들기 = **브랜드 계정** (개인 이름 대신 채널 이름으로 운영, 나중에 드라마 채널도 같은 계정 아래 따로 만들 수 있음)
- [ ] 채널 이름·핸들(@) 정하기 — 채널 약속(안): "살림이 조금 편해지는 실용템과 고르는 기준" ([youtube-shorts-coupang.md](youtube-shorts-coupang.md) §3)
- [ ] 휴대전화 인증 (YouTube 스튜디오 → 설정 → 채널 → 기능 사용 자격요건) — 맞춤 썸네일 등 고급 기능

**채널 꾸미기 (YouTube 스튜디오 → 맞춤설정)**
- [ ] 프로필 사진·배너 — 직접 만든 것 또는 상업 이용 가능한 이미지만
- [ ] 채널 설명: 무엇을 다루는지 + "일부 링크는 쿠팡 파트너스 활동으로, 이에 따른 일정액의 수수료를 제공받습니다" 같은 대가성 안내 (공식 문구는 6번에서 확인한 것으로)
- [ ] 링크: **상품 모음 페이지**(아직 없음, 만들면 추가) — 쇼츠 설명란·댓글 링크는 눌리지 않아서 프로필 링크로 유도

**업로드 기본값 (YouTube 스튜디오 → 설정 → 업로드 기본값)**
- [ ] 공개 상태 = **비공개** (CLAUDE.md: 항상 비공개 업로드 → 사람이 공개)
- [ ] 고급 설정 → "변경되거나 합성된 콘텐츠" 표시 기준 확인 — 실사처럼 보이는 AI 장면이 있을 때 표시. 일러스트(비실사)는 대상인지 공식 도움말로 확인 후 기록

**등록·기록**
- [ ] 쿠팡 파트너스 → 사이트 관리 → **채널 주소 추가 등록** (링크를 게시하는 곳은 전부 등록)
- [ ] Notion moruu 운영 허브에 채널 주소·핸들 기록

**2차(자동 업로드) 때 — 지금은 안 해도 됨**
- [ ] Google Cloud `moruu` 프로젝트 → **YouTube Data API v3** 사용 설정
- [ ] OAuth 동의 화면 → **프로덕션으로 게시** ("테스트" 상태면 refresh token 이 7일 뒤 만료) — 개인용은 미인증 경고만 뜨고 사용 가능
- [ ] OAuth 클라이언트 ID = **데스크톱 앱** → 토큰 발급 스크립트는 2차에서 만듦 (`channels/youtube`)
- [ ] 업로드 쿼터 확인 (Cloud Console → API → 할당량)

## 7. 나중에 (조건 충족 시)

- [ ] 쿠팡 파트너스 최종 승인 → Open API 키 발급 → Step 3
- [ ] TTS 도구 결정 → Step 4 (YouTube 쇼핑 쇼츠)
