# 직접 해야 할 일 (회사 PC에서 막힌 것)

> 코드는 다 준비됨. 아래는 사람이 계정·키를 넣어야 하는 단계. **개인 PC(또는 Mac)에서 순서대로.**
> 키·토큰은 대화창·커밋에 절대 붙여넣지 말고 `.env` / GitHub Secrets 에만.

## 0. 개인 PC 준비 (처음 한 번)

```bash
git clone https://github.com/day0ung/moruu.git   # 1번 push 이후
cd moruu
# Mac:      brew install uv
# Windows:  winget install --id=astral-sh.uv -e   (막히면 py -m pip install --user uv)
uv sync
uv run pytest -q          # 전부 통과해야 함
```
- `.env` 는 git에 없음 → 회사 PC의 `.env` 를 안전하게 옮기거나, 아래 4번으로 토큰 재발급

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

- [ ] https://www.notion.so/profile/integrations → 새 API 통합 → 이름 `moruu-bot`, 워크스페이스 "young님의 워크스페이스"
- [ ] 기능: 콘텐츠 **읽기·업데이트·삽입** → 저장 → 내부 통합 시크릿 복사
- [ ] Notion **moruu 운영** 페이지 → `···` → 연결 → `moruu-bot` 추가 (하위 DB 전부 적용)
- [ ] `.env` 에 직접 입력:
```
NOTION_TOKEN=<복사한 시크릿>
NOTION_DB_CONTENT=d21f8e04b3c0484083441208c4803055
NOTION_DB_METRICS=cf3660bfccba4e039154da7f906825d2
NOTION_DB_FAILURES=9704e07520644ec2b87ded4c93f15ff0
MORUU_DAILY_CAP=3
```
- [ ] 연결 확인 (값은 출력 안 됨):
```bash
uv run python -c "from dotenv import load_dotenv; import os; load_dotenv(); from core.config import Settings; Settings.from_env(os.environ); print('ok')"
```

## 3. 첫 게시 시험 (로컬)

- [ ] Notion 콘텐츠 DB의 예시 글(`TH-LIVING-20261101-001`)에서 `예약시각` = 지금, `status` = **APPROVED**
- [ ] `uv run python -m pipelines.threads_post --dry-run` → `[dry-run] 게시 예정: TH-LIVING-20261101-001`
- [ ] `uv run python -m pipelines.threads_post --only publish` → Threads 앱에 글 확인, Notion status=POSTED·게시ID 채워짐
- [ ] 링크 글 1개 시험: `링크` + `대가성문구` 채우고 같은 순서로 → 첫 댓글에 링크+문구 확인
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

## 7. 나중에 (조건 충족 시)

- [ ] 쿠팡 파트너스 최종 승인 → Open API 키 발급 → Step 3
- [ ] TTS 도구 결정 → Step 4 (YouTube 쇼핑 쇼츠)
