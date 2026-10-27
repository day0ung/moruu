# Threads 반자동 게시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notion 콘텐츠 DB에서 사람이 `APPROVED`로 바꾼 Threads 글을 예약 시각 이후 자동 게시하고(첫 댓글에 링크+대가성 문구), 24h/72h/7d 인사이트를 Notion 성과 DB에 기록한다. GitHub Actions에서 하루 2회 + 수동 실행.

**Architecture:** `core/`(설정·로깅·Notion 저장소·안전 규칙) + `channels/threads/`(Threads API 클라이언트·토큰 갱신) + `pipelines/threads_post/`(게시·수집 흐름, CLI). 파이프라인은 저장소/클라이언트를 인자로 받아 가짜 객체로 테스트한다. HTTP는 `httpx`, 테스트는 `httpx.MockTransport`.

**Tech Stack:** Python 3.12, uv, httpx, python-dotenv, pytest, Notion API (`Notion-Version: 2022-06-28`), Threads Graph API v1.0, GitHub Actions

**Spec:** `docs/PLAN.md` (§2 레포 구조, §3 Notion, §4 Step 0~2, §7 안전 규칙, §8 결정)

## Global Constraints

- Python `>=3.12`, 패키지 관리는 `uv` (`uv sync`, `uv run`)
- 의존성은 `httpx`, `python-dotenv` (런타임) + `pytest` (dev)만
- 키·토큰은 `.env`(로컬) / GitHub Secrets(Actions)에만. 코드·로그·커밋에 값 금지
- **`status=APPROVED`인 글만 게시.** DRAFT 등은 절대 게시하지 않음. APPROVED는 사람만 바꿈
- 링크가 있는데 대가성 문구가 없으면 게시하지 않음 (FAILED 처리)
- 하루 게시 상한 기본 3 (`MORUU_DAILY_CAP`), 수익 글 연속 게시 금지
- 재시도 최대 2회. 토큰 만료(Threads error code 190)는 즉시 실행 중단
- Actions 실행: KST 08:00 / 20:00 (`cron: "0 23 * * *"`, `"0 11 * * *"`) + `workflow_dispatch`, `concurrency` 로 중복 실행 방지
- 기존 `../gomgom/threads-auto`, `../gomgom/threads-auth-page`는 **복사만** (원본 유지)
- 폴더 이름은 Python 패키지 규칙상 `pipelines/threads_post` (PLAN.md의 `threads-post`와 같은 것)

---

## File Structure

```
moruu/
├─ pyproject.toml                         # uv 프로젝트 (빌드 없음, pytest 경로 설정)
├─ .gitignore / .env.example / CLAUDE.md
├─ apps/threads-auth-page/index.html      # 복사
├─ core/
│  ├─ __init__.py
│  ├─ config.py        # Settings.from_env — 필수 환경변수 검증
│  ├─ log.py           # setup_logging — 키 마스킹, httpx 로그 억제
│  ├─ schema.py        # Notion 속성 이름 상수 + 속성 값 빌더
│  ├─ models.py        # KST, Post, parse_post (Notion page → Post)
│  ├─ notion_store.py  # NotionStore — 조회/상태 변경/성과·실패 기록
│  └─ safety.py        # blocking_problems, hold_reasons
├─ channels/
│  ├─ __init__.py
│  └─ threads/
│     ├─ __init__.py
│     ├─ client.py     # ThreadsClient, ThreadsError, TOKEN_EXPIRED
│     ├─ token.py      # needs_refresh, update_env_file, persist_token
│     └─ scripts/get_token.ps1   # 복사 + .env 경로 수정
├─ pipelines/
│  ├─ __init__.py
│  └─ threads_post/
│     ├─ __init__.py
│     ├─ publish.py    # run_publish
│     ├─ collect.py    # run_collect
│     └─ __main__.py   # CLI: python -m pipelines.threads_post
├─ tests/
│  ├─ fakes.py         # FakeStore, FakeClient, make_post
│  ├─ core/test_config.py, test_log.py, test_models.py, test_notion_store.py, test_safety.py
│  ├─ channels/test_threads_client.py, test_threads_token.py
│  └─ pipelines/test_publish.py, test_collect.py
├─ docs/notion-schema.md                  # DB ID·속성 기록
└─ .github/workflows/threads.yml
```

---

### Task 1: 레포 뼈대 + 기존 Threads 파일 가져오기

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `CLAUDE.md`, `core/__init__.py`, `channels/__init__.py`, `channels/threads/__init__.py`, `pipelines/__init__.py`, `pipelines/threads_post/__init__.py`, `tests/test_smoke.py`
- Copy: `../gomgom/threads-auto/get_token.ps1` → `channels/threads/scripts/get_token.ps1`, `../gomgom/threads-auth-page/index.html` → `apps/threads-auth-page/index.html`, `../gomgom/threads-auto/.env` → `.env`

**Interfaces:**
- Produces: `uv run pytest` 가 동작하는 프로젝트, 루트 `.env`

- [ ] **Step 1: 문서 커밋 후 작업 브랜치 생성**

```bash
cd /c/apti_doc/book/moruu
git add README.md docs/
git commit -m "docs: 레포 계획과 Threads 반자동 구현 계획"
git switch -c feat/threads-semi-auto
```

- [ ] **Step 2: uv 설치 확인**

Run: `uv --version`
없으면: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` 후 터미널 재시작

- [ ] **Step 3: `pyproject.toml`**

```toml
[project]
name = "moruu"
version = "0.1.0"
description = "쇼핑 콘텐츠 반자동화 (Threads · 쿠팡 · YouTube)"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "tests"]
```

- [ ] **Step 4: `.gitignore`**

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
logs/
assets/raw/
.idea/
```

- [ ] **Step 5: `.env.example`**

```dotenv
# Threads (channels/threads/scripts/get_token.ps1 이 채움)
THREADS_APP_ID=
THREADS_APP_SECRET=
THREADS_USER_ID=
THREADS_ACCESS_TOKEN=
THREADS_TOKEN_ISSUED=2026-10-27

# Notion (Internal Integration 토큰 + DB ID)
NOTION_TOKEN=
NOTION_DB_CONTENT=
NOTION_DB_METRICS=
NOTION_DB_FAILURES=

# 운영
MORUU_DAILY_CAP=3
```

- [ ] **Step 6: `CLAUDE.md`**

```markdown
# moruu — Claude 작업 규칙

계획: docs/PLAN.md · 구조 그림: README.md · 근거 자료: ../gomgom/정리/

## 절대 규칙
- 키·토큰 값을 출력·커밋·로그하지 않는다. `.env`는 키 이름만 확인한다.
- `status=APPROVED`는 사람만 바꾼다. Claude는 DRAFT까지만 만든다.
- 링크 글에는 대가성 문구가 링크 바로 옆에 있어야 한다.
- 써보지 않은 경험을 1인칭으로 쓰지 않는다. 숫자·가격은 확인된 것만. "최고·필수·무조건·혁신적" 금지.
- YouTube는 항상 비공개 업로드 → 사람이 공개.
- 게시 시간 랜덤 위장 등 탐지 회피 설계를 하지 않는다.

## 구조
- core/ 공통 (설정·로깅·Notion·안전 규칙), channels/ 플랫폼 클라이언트, pipelines/ 콘텐츠 흐름
- pipelines끼리 import 금지

## 명령
- 테스트: `uv run pytest`
- 게시/수집 시험: `uv run python -m pipelines.threads_post --dry-run`
- Notion 속성 이름은 core/schema.py 와 docs/notion-schema.md 를 같이 고친다.
```

- [ ] **Step 7: 패키지 폴더와 smoke 테스트**

빈 `__init__.py` 5개 생성: `core/`, `channels/`, `channels/threads/`, `pipelines/`, `pipelines/threads_post/`

`tests/test_smoke.py`:
```python
import core
import channels.threads
import pipelines.threads_post


def test_packages_import():
    assert core and channels.threads and pipelines.threads_post
```

- [ ] **Step 8: 기존 파일 복사 (원본 유지)**

```bash
mkdir -p channels/threads/scripts apps/threads-auth-page
cp ../gomgom/threads-auto/get_token.ps1 channels/threads/scripts/get_token.ps1
cp ../gomgom/threads-auth-page/index.html apps/threads-auth-page/index.html
cp ../gomgom/threads-auto/.env .env
```
`.env` 내용은 열지 말고 키 이름만 확인: `sed -E 's/=.*/=<redacted>/' .env`

- [ ] **Step 9: `get_token.ps1` 의 .env 경로를 레포 루트로**

`channels/threads/scripts/get_token.ps1` 에서
```powershell
$envPath = Join-Path $PSScriptRoot '.env'
```
를
```powershell
$envPath = Join-Path $PSScriptRoot '..\..\..\.env'
```
로 변경.

- [ ] **Step 10: 설치 + 테스트**

Run: `uv sync && uv run pytest -v`
Expected: `test_packages_import PASSED`, `uv.lock` 생성

- [ ] **Step 11: 커밋 (.env 제외 확인)**

```bash
git status --short   # .env 가 목록에 없어야 함
git add pyproject.toml uv.lock .gitignore .env.example CLAUDE.md core channels pipelines tests apps
git commit -m "chore: uv 프로젝트 뼈대와 기존 Threads 인증 파일 가져오기"
```

---

### Task 2: 설정 로딩 + 키 마스킹 로깅

**Files:**
- Create: `core/config.py`, `core/log.py`
- Test: `tests/core/test_config.py`, `tests/core/test_log.py`

**Interfaces:**
- Produces:
  - `class ConfigError(Exception)`
  - `@dataclass(frozen=True) class Settings` 필드: `threads_user_id: str, threads_token: str, threads_token_issued: date, notion_token: str, notion_db_content: str, notion_db_metrics: str, notion_db_failures: str, daily_cap: int`
  - `Settings.from_env(env: Mapping[str, str]) -> Settings`
  - `setup_logging(secrets: Iterable[str]) -> logging.Logger` (이름 `"moruu"`)

- [ ] **Step 1: 실패 테스트 작성**

`tests/core/test_config.py`:
```python
from datetime import date

import pytest

from core.config import ConfigError, Settings

FULL = {
    "THREADS_USER_ID": "123",
    "THREADS_ACCESS_TOKEN": "tok",
    "THREADS_TOKEN_ISSUED": "2026-10-20",
    "NOTION_TOKEN": "ntn",
    "NOTION_DB_CONTENT": "db-c",
    "NOTION_DB_METRICS": "db-m",
    "NOTION_DB_FAILURES": "db-f",
}


def test_from_env_reads_all_fields():
    s = Settings.from_env(FULL)
    assert s.threads_user_id == "123"
    assert s.threads_token_issued == date(2026, 10, 20)
    assert s.notion_db_failures == "db-f"
    assert s.daily_cap == 3


def test_daily_cap_override():
    assert Settings.from_env({**FULL, "MORUU_DAILY_CAP": "5"}).daily_cap == 5


def test_missing_keys_are_listed_without_values():
    env = {k: v for k, v in FULL.items() if k not in ("NOTION_TOKEN", "NOTION_DB_CONTENT")}
    with pytest.raises(ConfigError) as e:
        Settings.from_env(env)
    assert "NOTION_TOKEN" in str(e.value)
    assert "NOTION_DB_CONTENT" in str(e.value)
    assert "tok" not in str(e.value)
```

`tests/core/test_log.py`:
```python
import logging

from core.log import setup_logging


def test_secrets_are_masked(caplog):
    log = setup_logging(["SECRET-TOKEN-123"])
    with caplog.at_level(logging.INFO, logger="moruu"):
        log.info("url ?access_token=%s", "SECRET-TOKEN-123")
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "access_token=***" in caplog.text


def test_httpx_request_logs_are_silenced():
    setup_logging([])
    assert logging.getLogger("httpx").level == logging.WARNING
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/core -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.config'`

- [ ] **Step 3: 구현**

`core/config.py`:
```python
"""환경변수 → Settings. 값은 절대 메시지에 넣지 않는다."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

REQUIRED = (
    "THREADS_USER_ID",
    "THREADS_ACCESS_TOKEN",
    "THREADS_TOKEN_ISSUED",
    "NOTION_TOKEN",
    "NOTION_DB_CONTENT",
    "NOTION_DB_METRICS",
    "NOTION_DB_FAILURES",
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    threads_user_id: str
    threads_token: str
    threads_token_issued: date
    notion_token: str
    notion_db_content: str
    notion_db_metrics: str
    notion_db_failures: str
    daily_cap: int = 3

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        missing = [k for k in REQUIRED if not env.get(k)]
        if missing:
            raise ConfigError("환경변수 없음: " + ", ".join(missing))
        return cls(
            threads_user_id=env["THREADS_USER_ID"],
            threads_token=env["THREADS_ACCESS_TOKEN"],
            threads_token_issued=date.fromisoformat(env["THREADS_TOKEN_ISSUED"]),
            notion_token=env["NOTION_TOKEN"],
            notion_db_content=env["NOTION_DB_CONTENT"],
            notion_db_metrics=env["NOTION_DB_METRICS"],
            notion_db_failures=env["NOTION_DB_FAILURES"],
            daily_cap=int(env.get("MORUU_DAILY_CAP") or 3),
        )
```

`core/log.py`:
```python
"""로깅 — 키·토큰 마스킹. 파이프라인은 항상 "moruu" 로거 하나를 받아 쓴다."""
from __future__ import annotations

import logging
from collections.abc import Iterable


class MaskSecrets(logging.Filter):
    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 8]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for s in self._secrets:
            msg = msg.replace(s, "***")
        record.msg, record.args = msg, ()
        return True


def setup_logging(secrets: Iterable[str]) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx 는 INFO 에서 요청 URL(토큰 쿼리 포함)을 찍는다
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("moruu")
    log.setLevel(logging.INFO)
    for f in [f for f in log.filters if isinstance(f, MaskSecrets)]:
        log.removeFilter(f)
    log.addFilter(MaskSecrets(secrets))
    return log
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/core -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add core/config.py core/log.py tests/core
git commit -m "feat(core): 환경변수 설정 로딩과 키 마스킹 로깅"
```

---

### Task 3: Notion 스키마 상수 + Post 모델

**Files:**
- Create: `core/schema.py`, `core/models.py`
- Test: `tests/core/test_models.py`

**Interfaces:**
- Produces:
  - `core.schema`: 속성 이름 상수 `TITLE_ID, CHANNEL, ROLE, TEXT, LINK, DISCLOSURE, STATUS, SCHEDULED, POSTED_AT, MEDIA_ID, REPLY_ID, ERROR`, `COLLECTED: dict[int, str]`, 값 상수 `CH_THREADS, APPROVED, POSTED, FAILED, ROLE_REVENUE`, 성과 DB `M_*`, `MILESTONE_LABEL`, `METRIC_PROPS`, 실패 DB `F_*`, 빌더 `title(), rich(), select(), date(), number(), checkbox()`
  - `core.models`: `KST`, `@dataclass(frozen=True) Post(page_id, content_id, role, text, link: str|None, disclosure, scheduled_at: datetime|None, posted_at: datetime|None = None, media_id: str|None = None, collected: frozenset[int] = frozenset())`, `parse_post(page: dict) -> Post`

- [ ] **Step 1: 실패 테스트 작성**

`tests/core/test_models.py`:
```python
from datetime import datetime

from core import schema as S
from core.models import KST, parse_post


def sample_page(**props):
    base = {
        "content_id": {"title": [{"plain_text": "TH-LIVING-20261101-001"}]},
        "채널": {"select": {"name": "Threads"}},
        "역할": {"select": {"name": "수익"}},
        "본문": {"rich_text": [{"plain_text": "좁은 집 "}, {"plain_text": "수납 팁"}]},
        "링크": {"url": "https://link.coupang.com/a/abc"},
        "대가성문구": {"rich_text": [{"plain_text": "쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다."}]},
        "status": {"select": {"name": "APPROVED"}},
        "예약시각": {"date": {"start": "2026-11-01T08:00:00.000+09:00"}},
        "게시시각": {"date": None},
        "게시ID": {"rich_text": []},
        "수집_24h": {"checkbox": True},
        "수집_72h": {"checkbox": False},
        "수집_7d": {"checkbox": False},
    }
    base.update(props)
    return {"id": "page-1", "properties": base}


def test_parse_post_reads_properties():
    p = parse_post(sample_page())
    assert p.page_id == "page-1"
    assert p.content_id == "TH-LIVING-20261101-001"
    assert p.role == "수익"
    assert p.text == "좁은 집 수납 팁"
    assert p.link == "https://link.coupang.com/a/abc"
    assert p.scheduled_at == datetime(2026, 11, 1, 8, 0, tzinfo=KST)
    assert p.posted_at is None
    assert p.media_id is None
    assert p.collected == frozenset({24})


def test_date_without_time_is_kst():
    p = parse_post(sample_page(**{"예약시각": {"date": {"start": "2026-11-01"}}}))
    assert p.scheduled_at.tzinfo == KST


def test_empty_link_is_none():
    assert parse_post(sample_page(**{"링크": {"url": None}})).link is None


def test_builders_shape():
    assert S.select("POSTED") == {"select": {"name": "POSTED"}}
    assert S.rich("x") == {"rich_text": [{"text": {"content": "x"}}]}
    assert S.checkbox(True) == {"checkbox": True}
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/core/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.schema'`

- [ ] **Step 3: 구현**

`core/schema.py`:
```python
"""Notion 속성 이름과 값 빌더. Notion 에서 이름을 바꾸면 여기와 docs/notion-schema.md 를 같이 바꾼다."""
from __future__ import annotations

from datetime import datetime

# 콘텐츠 DB
TITLE_ID = "content_id"
CHANNEL = "채널"
ROLE = "역할"
TEXT = "본문"
LINK = "링크"
DISCLOSURE = "대가성문구"
STATUS = "status"
SCHEDULED = "예약시각"
POSTED_AT = "게시시각"
MEDIA_ID = "게시ID"
REPLY_ID = "댓글ID"
ERROR = "오류"
COLLECTED = {24: "수집_24h", 72: "수집_72h", 168: "수집_7d"}

CH_THREADS = "Threads"
APPROVED = "APPROVED"
POSTED = "POSTED"
FAILED = "FAILED"
ROLE_REVENUE = "수익"

# 성과 DB
M_TITLE = "기록"
M_CONTENT_ID = "content_id"
M_MILESTONE = "경과"
M_ACTUAL_H = "실제경과h"
M_COLLECTED_AT = "수집시각"
MILESTONE_LABEL = {24: "24h", 72: "72h", 168: "7d"}
METRIC_PROPS = {"views": "조회", "likes": "좋아요", "replies": "댓글", "reposts": "리포스트", "quotes": "인용"}

# 실패 로그 DB
F_TITLE = "요약"
F_CONTENT_ID = "content_id"
F_STEP = "step"
F_CODE = "error_code"
F_MESSAGE = "message"
F_RETRY = "retry_count"
F_FINAL = "final_status"
F_TIME = "time"

_MAX = 2000  # Notion rich_text 한 덩어리 최대 길이


def title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:_MAX]}}]}


def rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:_MAX]}}]}


def select(name: str) -> dict:
    return {"select": {"name": name}}


def date(dt: datetime) -> dict:
    return {"date": {"start": dt.isoformat()}}


def number(value: float) -> dict:
    return {"number": value}


def checkbox(value: bool) -> dict:
    return {"checkbox": value}
```

`core/models.py`:
```python
"""Notion 페이지 → Post."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core import schema as S

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Post:
    page_id: str
    content_id: str
    role: str
    text: str
    link: str | None
    disclosure: str
    scheduled_at: datetime | None
    posted_at: datetime | None = None
    media_id: str | None = None
    collected: frozenset[int] = frozenset()


def _plain(prop: dict) -> str:
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(i.get("plain_text", "") for i in items)


def _select(prop: dict) -> str:
    s = prop.get("select")
    return s["name"] if s else ""


def _date(prop: dict) -> datetime | None:
    d = prop.get("date")
    if not d:
        return None
    dt = datetime.fromisoformat(d["start"])
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def parse_post(page: dict) -> Post:
    props = page["properties"]

    def get(name: str) -> dict:
        return props.get(name) or {}

    return Post(
        page_id=page["id"],
        content_id=_plain(get(S.TITLE_ID)),
        role=_select(get(S.ROLE)),
        text=_plain(get(S.TEXT)),
        link=get(S.LINK).get("url") or None,
        disclosure=_plain(get(S.DISCLOSURE)),
        scheduled_at=_date(get(S.SCHEDULED)),
        posted_at=_date(get(S.POSTED_AT)),
        media_id=_plain(get(S.MEDIA_ID)) or None,
        collected=frozenset(h for h, name in S.COLLECTED.items() if get(name).get("checkbox")),
    )
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/core/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add core/schema.py core/models.py tests/core/test_models.py
git commit -m "feat(core): Notion 속성 스키마와 Post 모델"
```

---

### Task 4: Notion 저장소

**Files:**
- Create: `core/notion_store.py`
- Test: `tests/core/test_notion_store.py`

**Interfaces:**
- Consumes: `core.schema`, `core.models.Post`, `parse_post`
- Produces:
  - `@dataclass(frozen=True) DbIds(content: str, metrics: str, failures: str)`
  - `NotionStore(token: str, dbs: DbIds, http: httpx.Client | None = None)` 메서드:
    - `approved_threads_due(now: datetime) -> list[Post]`
    - `posted_threads_since(since: datetime) -> list[Post]`
    - `mark_posted(post: Post, media_id: str, reply_id: str | None, at: datetime) -> None`
    - `mark_failed(post: Post, error: str) -> None`
    - `mark_collected(post: Post, hours: list[int]) -> None`
    - `add_metrics(post: Post, hours: int, actual_hours: float, metrics: dict[str, int], at: datetime) -> None`
    - `log_failure(content_id: str, step: str, code: str, message: str, retries: int, final: str, at: datetime) -> None`

- [ ] **Step 1: 실패 테스트 작성**

`tests/core/test_notion_store.py`:
```python
import json
from datetime import datetime

import httpx

from core.models import KST, Post
from core.notion_store import API, DbIds, NotionStore

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=KST)


def make_store(responses):
    """responses: 요청 순서대로 돌려줄 JSON 목록. 보낸 요청은 store.sent 에 쌓인다."""
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append((req.method, req.url.path, json.loads(req.content or b"{}"), req.headers))
        return httpx.Response(200, json=responses.pop(0) if responses else {})

    http = httpx.Client(base_url=API, transport=httpx.MockTransport(handler))
    store = NotionStore("ntn-token", DbIds("db-c", "db-m", "db-f"), http=http)
    return store, sent


def page(pid, cid):
    return {
        "id": pid,
        "properties": {
            "content_id": {"title": [{"plain_text": cid}]},
            "본문": {"rich_text": [{"plain_text": "본문"}]},
            "status": {"select": {"name": "APPROVED"}},
        },
    }


def post():
    return Post("page-1", "TH-1", "수익", "본문", None, "", None)


def test_approved_due_filters_and_paginates():
    store, sent = make_store([
        {"results": [page("p1", "TH-1")], "has_more": True, "next_cursor": "c2"},
        {"results": [page("p2", "TH-2")], "has_more": False},
    ])
    posts = store.approved_threads_due(NOW)
    assert [p.content_id for p in posts] == ["TH-1", "TH-2"]
    method, path, body, headers = sent[0]
    assert (method, path) == ("POST", "/v1/databases/db-c/query")
    assert headers["Authorization"] == "Bearer ntn-token"
    assert headers["Notion-Version"] == "2022-06-28"
    conds = body["filter"]["and"]
    assert {"property": "status", "select": {"equals": "APPROVED"}} in conds
    assert {"property": "채널", "select": {"equals": "Threads"}} in conds
    assert {"property": "예약시각", "date": {"on_or_before": NOW.isoformat()}} in conds
    assert sent[1][2]["start_cursor"] == "c2"


def test_mark_posted_sets_status_ids_time():
    store, sent = make_store([{}])
    store.mark_posted(post(), "m1", "r1", NOW)
    method, path, body, _ = sent[0]
    assert (method, path) == ("PATCH", "/v1/pages/page-1")
    props = body["properties"]
    assert props["status"] == {"select": {"name": "POSTED"}}
    assert props["게시ID"]["rich_text"][0]["text"]["content"] == "m1"
    assert props["댓글ID"]["rich_text"][0]["text"]["content"] == "r1"
    assert props["게시시각"] == {"date": {"start": NOW.isoformat()}}


def test_add_metrics_creates_row_in_metrics_db():
    store, sent = make_store([{}])
    store.add_metrics(post(), 24, 30.5, {"views": 120, "likes": 4, "unknown": 9}, NOW)
    _, path, body, _ = sent[0]
    assert path == "/v1/pages"
    assert body["parent"] == {"database_id": "db-m"}
    props = body["properties"]
    assert props["경과"] == {"select": {"name": "24h"}}
    assert props["실제경과h"] == {"number": 30.5}
    assert props["조회"] == {"number": 120}
    assert "unknown" not in json.dumps(props)


def test_mark_collected_sets_checkboxes():
    store, sent = make_store([{}])
    store.mark_collected(post(), [24, 72])
    props = sent[0][2]["properties"]
    assert props == {"수집_24h": {"checkbox": True}, "수집_72h": {"checkbox": True}}


def test_log_failure_goes_to_failures_db():
    store, sent = make_store([{}])
    store.log_failure("TH-1", "post", "1", "boom", 2, "FAILED", NOW)
    body = sent[0][2]
    assert body["parent"] == {"database_id": "db-f"}
    assert body["properties"]["step"] == {"select": {"name": "post"}}
    assert body["properties"]["retry_count"] == {"number": 2}
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/core/test_notion_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.notion_store'`

- [ ] **Step 3: 구현**

`core/notion_store.py`:
```python
"""Notion API 저장소 — 무인 실행(Actions)용. 대화형 작업은 Notion MCP 로 한다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from core import schema as S
from core.models import Post, parse_post

API = "https://api.notion.com"
NOTION_VERSION = "2022-06-28"


@dataclass(frozen=True)
class DbIds:
    content: str
    metrics: str
    failures: str


class NotionStore:
    def __init__(self, token: str, dbs: DbIds, http: httpx.Client | None = None):
        self._dbs = dbs
        self._http = http or httpx.Client(base_url=API, timeout=30)
        self._headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        r = self._http.request(method, path, json=body, headers=self._headers)
        r.raise_for_status()
        return r.json()

    def _query(self, db_id: str, filter_: dict, sorts: list[dict]) -> list[dict]:
        body = {"filter": filter_, "sorts": sorts, "page_size": 100}
        pages: list[dict] = []
        while True:
            data = self._req("POST", f"/v1/databases/{db_id}/query", body)
            pages += data["results"]
            if not data.get("has_more"):
                return pages
            body["start_cursor"] = data["next_cursor"]

    def _threads(self, status: str, date_prop: str, op: str, when: datetime) -> list[Post]:
        filter_ = {"and": [
            {"property": S.STATUS, "select": {"equals": status}},
            {"property": S.CHANNEL, "select": {"equals": S.CH_THREADS}},
            {"property": date_prop, "date": {op: when.isoformat()}},
        ]}
        pages = self._query(self._dbs.content, filter_, [{"property": date_prop, "direction": "ascending"}])
        return [parse_post(p) for p in pages]

    def approved_threads_due(self, now: datetime) -> list[Post]:
        return self._threads(S.APPROVED, S.SCHEDULED, "on_or_before", now)

    def posted_threads_since(self, since: datetime) -> list[Post]:
        return self._threads(S.POSTED, S.POSTED_AT, "on_or_after", since)

    def _update(self, page_id: str, props: dict) -> None:
        self._req("PATCH", f"/v1/pages/{page_id}", {"properties": props})

    def _create(self, db_id: str, props: dict) -> None:
        self._req("POST", "/v1/pages", {"parent": {"database_id": db_id}, "properties": props})

    def mark_posted(self, post: Post, media_id: str, reply_id: str | None, at: datetime) -> None:
        props = {S.STATUS: S.select(S.POSTED), S.MEDIA_ID: S.rich(media_id), S.POSTED_AT: S.date(at)}
        if reply_id:
            props[S.REPLY_ID] = S.rich(reply_id)
        self._update(post.page_id, props)

    def mark_failed(self, post: Post, error: str) -> None:
        self._update(post.page_id, {S.STATUS: S.select(S.FAILED), S.ERROR: S.rich(error)})

    def mark_collected(self, post: Post, hours: list[int]) -> None:
        self._update(post.page_id, {S.COLLECTED[h]: S.checkbox(True) for h in hours})

    def add_metrics(self, post: Post, hours: int, actual_hours: float, metrics: dict[str, int], at: datetime) -> None:
        label = S.MILESTONE_LABEL[hours]
        props = {
            S.M_TITLE: S.title(f"{post.content_id} {label}"),
            S.M_CONTENT_ID: S.rich(post.content_id),
            S.M_MILESTONE: S.select(label),
            S.M_ACTUAL_H: S.number(actual_hours),
            S.M_COLLECTED_AT: S.date(at),
        }
        for key, value in metrics.items():
            if key in S.METRIC_PROPS:
                props[S.METRIC_PROPS[key]] = S.number(value)
        self._create(self._dbs.metrics, props)

    def log_failure(self, content_id: str, step: str, code: str, message: str,
                    retries: int, final: str, at: datetime) -> None:
        self._create(self._dbs.failures, {
            S.F_TITLE: S.title(f"{content_id} {step} {code}"),
            S.F_CONTENT_ID: S.rich(content_id),
            S.F_STEP: S.select(step),
            S.F_CODE: S.rich(code),
            S.F_MESSAGE: S.rich(message),
            S.F_RETRY: S.number(retries),
            S.F_FINAL: S.select(final),
            S.F_TIME: S.date(at),
        })
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/core/test_notion_store.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add core/notion_store.py tests/core/test_notion_store.py
git commit -m "feat(core): Notion API 저장소 (조회·상태 변경·성과·실패 기록)"
```

---

### Task 5: 안전 규칙

**Files:**
- Create: `core/safety.py`, `tests/fakes.py` (이 태스크에선 `make_post`만 사용)
- Test: `tests/core/test_safety.py`

**Interfaces:**
- Consumes: `core.models.Post`, `KST`, `core.schema.ROLE_REVENUE`
- Produces:
  - `THREADS_MAX_CHARS = 500`
  - `blocking_problems(post: Post) -> list[str]` — 고쳐야 하는 문제 (→ FAILED)
  - `hold_reasons(post: Post, recent: list[Post], daily_cap: int, now: datetime) -> list[str]` — 다음 실행으로 미룰 이유 (APPROVED 유지)
  - `tests/fakes.py`: `make_post(**overrides) -> Post`, `FakeStore`, `FakeClient` (Task 7·8에서 사용)

- [ ] **Step 1: `tests/fakes.py` 작성**

```python
"""파이프라인 테스트용 가짜 저장소·클라이언트."""
from dataclasses import replace
from datetime import datetime

from channels.threads.client import ThreadsError
from core.models import KST, Post

BASE_POST = Post(
    page_id="page-1",
    content_id="TH-LIVING-20261101-001",
    role="정보",
    text="좁은 집 수납 팁",
    link=None,
    disclosure="",
    scheduled_at=datetime(2026, 11, 1, 8, 0, tzinfo=KST),
)


def make_post(**overrides) -> Post:
    return replace(BASE_POST, **overrides)


class FakeStore:
    def __init__(self, due=(), recent=()):
        self.due = list(due)
        self.recent = list(recent)
        self.posted, self.failed, self.failures, self.metrics, self.collected = [], [], [], [], []

    def approved_threads_due(self, now):
        return list(self.due)

    def posted_threads_since(self, since):
        return [p for p in self.recent if p.posted_at and p.posted_at >= since]

    def mark_posted(self, post, media_id, reply_id, at):
        self.posted.append((post.content_id, media_id, reply_id))

    def mark_failed(self, post, error):
        self.failed.append((post.content_id, error))

    def log_failure(self, content_id, step, code, message, retries, final, at):
        self.failures.append((content_id, step, code, final))

    def add_metrics(self, post, hours, actual_hours, metrics, at):
        self.metrics.append((post.content_id, hours, actual_hours, metrics))

    def mark_collected(self, post, hours):
        self.collected.append((post.content_id, sorted(hours)))


class FakeClient:
    def __init__(self, fail_times=0, error_code="1", quota=250, insights=None):
        self.calls = []
        self.quota = quota
        self._fail = fail_times
        self._code = error_code
        self._insights = insights or {"views": 10}
        self._n = 0

    def quota_left(self):
        return self.quota

    def post_text(self, text, reply_to=None):
        self.calls.append((text, reply_to))
        if self._fail > 0:
            self._fail -= 1
            raise ThreadsError(self._code, "boom")
        self._n += 1
        return f"m{self._n}"

    def insights(self, media_id):
        self.calls.append(("insights", media_id))
        if self._fail > 0:
            self._fail -= 1
            raise ThreadsError(self._code, "boom")
        return dict(self._insights)
```

> `tests/fakes.py` 는 Task 6에서 만드는 `ThreadsError` 를 import 한다. pytest는 `test_*.py` 만 수집하므로 지금 만들어 둬도 문제없고, 이 태스크의 테스트는 `fakes` 를 import 하지 않는다 (Task 7·8에서 사용).

- [ ] **Step 2: 실패 테스트 작성**

`tests/core/test_safety.py`:
```python
from dataclasses import replace
from datetime import datetime, timedelta

from core.models import KST, Post
from core.safety import THREADS_MAX_CHARS, blocking_problems, hold_reasons

NOW = datetime(2026, 11, 1, 20, 0, tzinfo=KST)
P = Post("page-1", "TH-1", "정보", "본문", None, "", NOW)


def posted(cid, role, hours_ago):
    return replace(P, content_id=cid, role=role, posted_at=NOW - timedelta(hours=hours_ago), media_id="m")


def test_ok_post_has_no_problems():
    assert blocking_problems(P) == []
    assert hold_reasons(P, [], 3, NOW) == []


def test_empty_or_too_long_text_blocks():
    assert blocking_problems(replace(P, text="  "))
    assert blocking_problems(replace(P, text="가" * (THREADS_MAX_CHARS + 1)))


def test_link_without_disclosure_blocks():
    reasons = blocking_problems(replace(P, link="https://link.coupang.com/a/x", disclosure=""))
    assert any("대가성" in r for r in reasons)


def test_already_posted_blocks():
    assert blocking_problems(replace(P, media_id="m1"))


def test_daily_cap_holds_only_same_kst_day():
    today = [posted(f"T{i}", "정보", i + 1) for i in range(3)]
    assert hold_reasons(P, today, 3, NOW)
    yesterday = [posted(f"T{i}", "정보", 21 + i) for i in range(3)]
    assert hold_reasons(P, yesterday, 3, NOW) == []


def test_revenue_after_revenue_holds():
    rev = replace(P, role="수익", link="https://x", disclosure="문구")
    assert hold_reasons(rev, [posted("T0", "정보", 5), posted("T1", "수익", 2)], 3, NOW)
    assert hold_reasons(rev, [posted("T1", "수익", 5), posted("T2", "정보", 2)], 3, NOW) == []


def test_same_content_id_in_recent_is_held():
    assert blocking_problems(P) == []
    assert hold_reasons(P, [posted("TH-1", "정보", 1)], 3, NOW)
```

- [ ] **Step 3: 실패 확인**

Run: `uv run pytest tests/core/test_safety.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.safety'`

- [ ] **Step 4: 구현**

`core/safety.py`:
```python
"""게시 전 안전 규칙 (PLAN.md §7).
blocking_problems → 사람이 고쳐야 함 (FAILED). hold_reasons → 다음 실행으로 미룸 (APPROVED 유지)."""
from __future__ import annotations

from datetime import datetime

from core import schema as S
from core.models import KST, Post

THREADS_MAX_CHARS = 500


def blocking_problems(post: Post) -> list[str]:
    problems = []
    if not post.text.strip():
        problems.append("본문 비어 있음")
    if len(post.text) > THREADS_MAX_CHARS:
        problems.append(f"본문 {THREADS_MAX_CHARS}자 초과 ({len(post.text)}자)")
    if post.link and not post.disclosure.strip():
        problems.append("링크가 있는데 대가성문구 없음")
    if post.media_id:
        problems.append("이미 게시ID 있음")
    return problems


def hold_reasons(post: Post, recent: list[Post], daily_cap: int, now: datetime) -> list[str]:
    reasons = []
    done = [p for p in recent if p.posted_at]
    if any(p.content_id == post.content_id for p in done):
        reasons.append("같은 content_id 최근 게시됨")
    today = now.astimezone(KST).date()
    if sum(p.posted_at.astimezone(KST).date() == today for p in done) >= daily_cap:
        reasons.append(f"하루 상한 {daily_cap}개 도달")
    if post.role == S.ROLE_REVENUE and done:
        last = max(done, key=lambda p: p.posted_at)
        if last.role == S.ROLE_REVENUE:
            reasons.append("수익 글 연속 금지")
    return reasons
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/core/test_safety.py -v`
Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add core/safety.py tests/core/test_safety.py tests/fakes.py
git commit -m "feat(core): 게시 전 안전 규칙과 테스트용 가짜 객체"
```

---

### Task 6: Threads API 클라이언트 + 토큰 갱신

**Files:**
- Create: `channels/threads/client.py`, `channels/threads/token.py`
- Test: `tests/channels/test_threads_client.py`, `tests/channels/test_threads_token.py`

**Interfaces:**
- Produces:
  - `BASE = "https://graph.threads.net"`, `TOKEN_EXPIRED = "190"`
  - `class ThreadsError(Exception)` 속성 `code: str`, `message: str`
  - `ThreadsClient(user_id: str, token: str, http: httpx.Client | None = None)`:
    - `post_text(text: str, reply_to: str | None = None) -> str` (게시된 media_id)
    - `quota_left() -> int`
    - `insights(media_id: str) -> dict[str, int]`
    - `refresh_token() -> tuple[str, int]` (새 토큰, 남은 초)
  - `channels.threads.token`: `REFRESH_AFTER_DAYS = 50`, `needs_refresh(issued: date, today: date) -> bool`, `update_env_file(path: Path, updates: dict[str, str]) -> None`, `persist_token(token: str, issued: date, *, env_path: Path, environ: Mapping[str, str], run=subprocess.run) -> None`

- [ ] **Step 1: 실패 테스트 작성**

`tests/channels/test_threads_client.py`:
```python
import httpx
import pytest

from channels.threads.client import BASE, ThreadsClient, ThreadsError


def make(handler):
    http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    return ThreadsClient("123", "SECRET-TOKEN", http=http)


def test_post_text_creates_container_then_publishes():
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, dict(req.url.params)))
        return httpx.Response(200, json={"id": "c1" if req.url.path.endswith("/threads") else "m1"})

    assert make(handler).post_text("안녕", reply_to="m0") == "m1"
    method, path, params = seen[0]
    assert (method, path) == ("POST", "/v1.0/123/threads")
    assert params["media_type"] == "TEXT"
    assert params["text"] == "안녕"
    assert params["reply_to_id"] == "m0"
    assert params["access_token"] == "SECRET-TOKEN"
    assert seen[1][1] == "/v1.0/123/threads_publish"
    assert seen[1][2]["creation_id"] == "c1"


def test_error_has_code_and_no_token():
    def handler(req):
        return httpx.Response(400, json={"error": {"code": 190, "message": "Error validating access token"}})

    with pytest.raises(ThreadsError) as e:
        make(handler).post_text("x")
    assert e.value.code == "190"
    assert "SECRET-TOKEN" not in str(e.value)


def test_non_json_error_uses_status():
    with pytest.raises(ThreadsError) as e:
        make(lambda req: httpx.Response(502, text="bad gateway")).quota_left()
    assert e.value.code == "502"


def test_quota_left():
    body = {"data": [{"quota_usage": 4, "config": {"quota_total": 250}}]}
    assert make(lambda req: httpx.Response(200, json=body)).quota_left() == 246


def test_insights_reads_values_and_total_value():
    body = {"data": [
        {"name": "views", "values": [{"value": 42}]},
        {"name": "likes", "total_value": {"value": 3}},
    ]}
    seen = []

    def handler(req):
        seen.append(req.url)
        return httpx.Response(200, json=body)

    assert make(handler).insights("m1") == {"views": 42, "likes": 3}
    assert seen[0].path == "/v1.0/m1/insights"
    assert seen[0].params["metric"] == "views,likes,replies,reposts,quotes"


def test_refresh_token():
    def handler(req):
        assert req.url.path == "/refresh_access_token"
        assert req.url.params["grant_type"] == "th_refresh_token"
        return httpx.Response(200, json={"access_token": "NEW", "expires_in": 5184000})

    assert make(handler).refresh_token() == ("NEW", 5184000)
```

`tests/channels/test_threads_token.py`:
```python
from datetime import date

from channels.threads.token import needs_refresh, persist_token, update_env_file


def test_needs_refresh_after_50_days():
    assert not needs_refresh(date(2026, 10, 1), date(2026, 11, 19))
    assert needs_refresh(date(2026, 10, 1), date(2026, 11, 20))


def test_update_env_file_replaces_and_keeps_others(tmp_path):
    env = tmp_path / ".env"
    env.write_text("THREADS_APP_ID=1\r\nTHREADS_ACCESS_TOKEN=old\r\n# 메모\r\n", encoding="utf-8")
    update_env_file(env, {"THREADS_ACCESS_TOKEN": "new", "THREADS_TOKEN_ISSUED": "2026-11-20"})
    assert env.read_text(encoding="utf-8").splitlines() == [
        "THREADS_APP_ID=1",
        "THREADS_ACCESS_TOKEN=new",
        "# 메모",
        "THREADS_TOKEN_ISSUED=2026-11-20",
    ]


def test_persist_token_local_writes_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    persist_token("new", date(2026, 11, 20), env_path=env, environ={})
    assert "THREADS_ACCESS_TOKEN=new" in env.read_text(encoding="utf-8")


def test_persist_token_in_actions_uses_gh_secret(tmp_path):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw["input"], kw["env"]["GH_TOKEN"]))

    environ = {"GITHUB_ACTIONS": "true", "GH_PAT": "pat", "GITHUB_REPOSITORY": "me/moruu"}
    persist_token("new", date(2026, 11, 20), env_path=tmp_path / ".env", environ=environ, run=fake_run)
    assert calls[0] == (["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", "me/moruu"], "new", "pat")
    assert calls[1][0][3] == "THREADS_TOKEN_ISSUED"
    assert calls[1][1] == "2026-11-20"
    assert not (tmp_path / ".env").exists()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/channels -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'channels.threads.client'`

- [ ] **Step 3: 구현**

`channels/threads/client.py`:
```python
"""Threads Graph API v1.0 — 텍스트 게시·답글·한도·인사이트·토큰 갱신."""
from __future__ import annotations

import httpx

BASE = "https://graph.threads.net"
TOKEN_EXPIRED = "190"
METRICS = "views,likes,replies,reposts,quotes"


class ThreadsError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class ThreadsClient:
    def __init__(self, user_id: str, token: str, http: httpx.Client | None = None):
        self._uid = user_id
        self._token = token
        self._http = http or httpx.Client(base_url=BASE, timeout=30)

    def _call(self, method: str, path: str, **params) -> dict:
        r = self._http.request(method, path, params={**params, "access_token": self._token})
        if r.is_error:
            try:
                err = r.json().get("error", {})
            except ValueError:
                err = {}
            raise ThreadsError(str(err.get("code", r.status_code)), err.get("message", r.reason_phrase))
        return r.json()

    def post_text(self, text: str, reply_to: str | None = None) -> str:
        params = {"media_type": "TEXT", "text": text}
        if reply_to:
            params["reply_to_id"] = reply_to
        creation_id = self._call("POST", f"/v1.0/{self._uid}/threads", **params)["id"]
        return self._call("POST", f"/v1.0/{self._uid}/threads_publish", creation_id=creation_id)["id"]

    def quota_left(self) -> int:
        data = self._call("GET", f"/v1.0/{self._uid}/threads_publishing_limit", fields="quota_usage,config")
        d = data["data"][0]
        return d["config"]["quota_total"] - d["quota_usage"]

    def insights(self, media_id: str) -> dict[str, int]:
        data = self._call("GET", f"/v1.0/{media_id}/insights", metric=METRICS)
        out = {}
        for m in data["data"]:
            out[m["name"]] = m["values"][0]["value"] if "values" in m else m["total_value"]["value"]
        return out

    def refresh_token(self) -> tuple[str, int]:
        data = self._call("GET", "/refresh_access_token", grant_type="th_refresh_token")
        return data["access_token"], int(data["expires_in"])
```

`channels/threads/token.py`:
```python
"""장기 토큰(60일) 갱신 — 50일 지나면 갱신하고 .env 또는 GitHub Secret 에 저장."""
from __future__ import annotations

import subprocess
from collections.abc import Mapping
from datetime import date
from pathlib import Path

REFRESH_AFTER_DAYS = 50


def needs_refresh(issued: date, today: date) -> bool:
    return (today - issued).days >= REFRESH_AFTER_DAYS


def update_env_file(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen, out = set(), []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def persist_token(token: str, issued: date, *, env_path: Path, environ: Mapping[str, str],
                  run=subprocess.run) -> None:
    updates = {"THREADS_ACCESS_TOKEN": token, "THREADS_TOKEN_ISSUED": issued.isoformat()}
    if environ.get("GITHUB_ACTIONS") == "true":
        gh_env = {**environ, "GH_TOKEN": environ["GH_PAT"]}
        for key, value in updates.items():
            run(["gh", "secret", "set", key, "--repo", environ["GITHUB_REPOSITORY"]],
                input=value, text=True, check=True, capture_output=True, env=gh_env)
    else:
        update_env_file(env_path, updates)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/channels -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add channels/threads/client.py channels/threads/token.py tests/channels
git commit -m "feat(threads): API 클라이언트와 장기 토큰 갱신"
```

---

### Task 6b: 토큰 최초 발급을 Python으로 (`get_token.ps1` 대체, Mac 지원)

**Files:**
- Create: `channels/threads/get_token.py`
- Modify: `channels/threads/token.py` (`update_env_file` 에 `remove` 인자 추가)
- Delete: `channels/threads/scripts/get_token.ps1` (폴더가 비면 폴더도)
- Modify: `CLAUDE.md` (명령 목록에 토큰 발급 추가)
- Test: `tests/channels/test_get_token.py`, `tests/channels/test_threads_token.py` (테스트 1개 추가)

**Interfaces:**
- Consumes: `channels.threads.client.BASE`, `ThreadsError`, `channels.threads.token.update_env_file`
- Produces:
  - `update_env_file(path: Path, updates: dict[str, str], remove: Iterable[str] = ()) -> None`
  - `REDIRECT_URI = "https://threads-auth.netlify.app/"`
  - `clean_code(code: str) -> str` (끝의 `#_` 제거, 공백 제거)
  - `@dataclass(frozen=True) Issued(token: str, expires_in: int, user_id: str, username: str)`
  - `exchange_code(http: httpx.Client, app_id: str, app_secret: str, code: str) -> Issued`
  - `main() -> int` — 실행: `uv run python -m channels.threads.get_token`

흐름 (기존 `get_token.ps1` 과 동일):
1. 루트 `.env` 읽기 (`dotenv_values`). `THREADS_APP_ID` 필수
2. `THREADS_APP_SECRET` 이 없으면 `getpass` 로 입력받음 (화면에 안 보임), `.env` 에 저장
3. `THREADS_AUTH_CODE` 가 없으면 `input` 으로 입력받음 (threads-auth-page 에서 복사한 코드)
4. 코드 → 단기 토큰 (`POST /oauth/access_token`, form) → 장기 토큰 (`GET /access_token`, `th_exchange_token`) → `GET /v1.0/me?fields=id,username`
5. `.env` 갱신: `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `THREADS_TOKEN_ISSUED`(오늘), `THREADS_AUTH_CODE` 삭제 (한 번 쓰면 끝)
6. 출력: `성공: @username / 유효기간 N일` — **토큰·시크릿은 절대 출력하지 않음**. 실패 시 `실패: [code] message`, 종료 코드 1

- [ ] **Step 1: 실패 테스트 작성**

`tests/channels/test_threads_token.py` 에 추가:
```python
def test_update_env_file_can_remove_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nTHREADS_AUTH_CODE=abc\nB=2\n", encoding="utf-8")
    update_env_file(env, {"B": "3"}, remove=["THREADS_AUTH_CODE"])
    assert env.read_text(encoding="utf-8").splitlines() == ["A=1", "B=3"]
```

`tests/channels/test_get_token.py`:
```python
import httpx
import pytest

from channels.threads.client import BASE, ThreadsError
from channels.threads.get_token import REDIRECT_URI, clean_code, exchange_code


def test_clean_code_strips_suffix_and_spaces():
    assert clean_code(" AQBx123#_ \n") == "AQBx123"
    assert clean_code("AQBx123") == "AQBx123"


def make_http(handler):
    return httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))


def test_exchange_code_runs_three_steps():
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path == "/oauth/access_token":
            return httpx.Response(200, json={"access_token": "SHORT", "user_id": 1})
        if req.url.path == "/access_token":
            return httpx.Response(200, json={"access_token": "LONG", "expires_in": 5183944})
        return httpx.Response(200, json={"id": "999", "username": "moruu_home"})

    issued = exchange_code(make_http(handler), "app1", "sec1", "CODE")
    assert issued.token == "LONG"
    assert issued.expires_in == 5183944
    assert (issued.user_id, issued.username) == ("999", "moruu_home")

    form = dict(httpx.QueryParams(seen[0].content.decode()))
    assert seen[0].method == "POST"
    assert form == {
        "client_id": "app1",
        "client_secret": "sec1",
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": "CODE",
    }
    assert seen[1].url.params["grant_type"] == "th_exchange_token"
    assert seen[1].url.params["access_token"] == "SHORT"
    assert seen[2].url.path == "/v1.0/me"
    assert seen[2].url.params["access_token"] == "LONG"


def test_exchange_code_error_has_no_secret():
    def handler(req):
        return httpx.Response(400, json={"error": {"code": 100, "message": "Invalid code"}})

    with pytest.raises(ThreadsError) as e:
        exchange_code(make_http(handler), "app1", "sec1", "CODE")
    assert e.value.code == "100"
    assert "sec1" not in str(e.value)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/channels -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'channels.threads.get_token'`, `TypeError: update_env_file() got an unexpected keyword argument 'remove'`

- [ ] **Step 3: `update_env_file` 수정 (`channels/threads/token.py`)**

```python
def update_env_file(path: Path, updates: dict[str, str], remove: Iterable[str] = ()) -> None:
    drop = set(remove)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen, out = set(), []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and key in drop:
            continue
        if "=" in line and key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
```
import 줄을 `from collections.abc import Iterable, Mapping` 로 변경.

- [ ] **Step 4: `channels/threads/get_token.py` 구현**

```python
"""Threads 장기 토큰 최초 발급 (get_token.ps1 대체, Windows·Mac 공통).
실행: uv run python -m channels.threads.get_token
threads-auth-page 에서 받은 인증 코드 → 단기 토큰 → 장기 토큰 → .env 저장."""
from __future__ import annotations

import getpass
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from dotenv import dotenv_values

from channels.threads.client import BASE, ThreadsError
from channels.threads.token import update_env_file

REDIRECT_URI = "https://threads-auth.netlify.app/"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Issued:
    token: str
    expires_in: int
    user_id: str
    username: str


def clean_code(code: str) -> str:
    code = code.strip()
    return code[:-2] if code.endswith("#_") else code


def _json(r: httpx.Response) -> dict:
    if r.is_error:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        raise ThreadsError(str(err.get("code", r.status_code)), err.get("message", r.reason_phrase))
    return r.json()


def exchange_code(http: httpx.Client, app_id: str, app_secret: str, code: str) -> Issued:
    short = _json(http.post("/oauth/access_token", data={
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }))["access_token"]
    long = _json(http.get("/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short,
    }))
    me = _json(http.get("/v1.0/me", params={"fields": "id,username", "access_token": long["access_token"]}))
    return Issued(long["access_token"], int(long["expires_in"]), str(me["id"]), me["username"])


def main() -> int:
    cfg = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    app_id = cfg.get("THREADS_APP_ID")
    if not app_id:
        print(f"THREADS_APP_ID 값이 비어 있습니다 ({ENV_PATH} 확인)")
        return 1
    updates: dict[str, str] = {}
    secret = cfg.get("THREADS_APP_SECRET")
    if not secret:
        secret = getpass.getpass("Threads 앱 시크릿 붙여넣기 (화면에 안 보임): ").strip()
        updates["THREADS_APP_SECRET"] = secret
    code = cfg.get("THREADS_AUTH_CODE") or input("인증 코드 붙여넣기: ")
    try:
        with httpx.Client(base_url=BASE, timeout=30) as http:
            issued = exchange_code(http, app_id, secret, clean_code(code))
    except ThreadsError as e:
        print(f"실패: {e}")
        return 1
    updates |= {
        "THREADS_USER_ID": issued.user_id,
        "THREADS_ACCESS_TOKEN": issued.token,
        "THREADS_TOKEN_ISSUED": date.today().isoformat(),
    }
    update_env_file(ENV_PATH, updates, remove=["THREADS_AUTH_CODE"])
    print(f"성공: @{issued.username} / 유효기간 {issued.expires_in // 86400}일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/channels -v`
Expected: 14 passed (기존 10 + 추가 4)

- [ ] **Step 6: ps1 삭제 + CLAUDE.md**

```bash
git rm channels/threads/scripts/get_token.ps1
```
`CLAUDE.md` 의 `## 명령` 에 한 줄 추가:
```markdown
- Threads 토큰 최초 발급/재발급: threads-auth-page 에서 코드 복사 → `uv run python -m channels.threads.get_token`
```

- [ ] **Step 7: 전체 테스트 + 커밋**

Run: `uv run pytest -q`

```bash
git add channels/threads/get_token.py channels/threads/token.py tests/channels CLAUDE.md
git commit -m "feat(threads): 토큰 최초 발급을 Python으로 이식 (Windows·Mac 공통)"
```

---

### Task 7: 게시 파이프라인

**Files:**
- Create: `pipelines/threads_post/publish.py`
- Test: `tests/pipelines/test_publish.py`

**Interfaces:**
- Consumes: `NotionStore` 메서드(`approved_threads_due`, `posted_threads_since`, `mark_posted`, `mark_failed`, `log_failure`), `ThreadsClient.post_text`, `quota_left`, `ThreadsError`, `TOKEN_EXPIRED`, `blocking_problems`, `hold_reasons`
- Produces:
  - `MAX_RETRY = 2`, `RETRY_WAIT_SEC = 5`
  - `reply_text(post: Post) -> str`
  - `run_publish(store, client, daily_cap: int, now: datetime, log: logging.Logger, *, dry_run: bool = False, sleep=time.sleep) -> list[str]` (게시한 content_id 목록). 토큰 만료 시 `ThreadsError(code="190")` 를 그대로 올림

- [ ] **Step 1: 실패 테스트 작성**

`tests/pipelines/test_publish.py`:
```python
import logging
from datetime import datetime, timedelta

import pytest

from channels.threads.client import ThreadsError
from core.models import KST
from fakes import FakeClient, FakeStore, make_post
from pipelines.threads_post.publish import run_publish

NOW = datetime(2026, 11, 1, 8, 5, tzinfo=KST)
LOG = logging.getLogger("moruu")
LINK = dict(role="수익", link="https://link.coupang.com/a/x", disclosure="쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다.")


def run(store, client, **kw):
    return run_publish(store, client, 3, NOW, LOG, sleep=lambda s: None, **kw)


def test_posts_body_then_link_reply():
    store, client = FakeStore(due=[make_post(**LINK)]), FakeClient()
    assert run(store, client) == ["TH-LIVING-20261101-001"]
    assert client.calls[0] == ("좁은 집 수납 팁", None)
    assert client.calls[1] == (LINK["link"] + "\n\n" + LINK["disclosure"], "m1")
    assert store.posted == [("TH-LIVING-20261101-001", "m1", "m2")]


def test_post_without_link_has_no_reply():
    store, client = FakeStore(due=[make_post()]), FakeClient()
    run(store, client)
    assert len(client.calls) == 1
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]


def test_missing_disclosure_fails_without_posting():
    store, client = FakeStore(due=[make_post(link="https://x", disclosure="")]), FakeClient()
    assert run(store, client) == []
    assert client.calls == []
    assert "대가성" in store.failed[0][1]


def test_daily_cap_holds_without_failing():
    recent = [make_post(content_id=f"T{i}", posted_at=NOW - timedelta(minutes=10 + i), media_id="m") for i in range(3)]
    store, client = FakeStore(due=[make_post()], recent=recent), FakeClient()
    assert run(store, client) == []
    assert client.calls == [] and store.failed == []


def test_second_revenue_post_in_same_run_is_held():
    a = make_post(content_id="A", **LINK)
    b = make_post(content_id="B", page_id="page-2", **LINK)
    store, client = FakeStore(due=[a, b]), FakeClient()
    assert run(store, client) == ["A"]


def test_retries_then_succeeds():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=2)
    assert run(store, client) == ["TH-LIVING-20261101-001"]
    assert len(client.calls) == 3


def test_gives_up_after_retries():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=3)
    assert run(store, client) == []
    assert store.failed and store.failures == [("TH-LIVING-20261101-001", "post", "1", "FAILED")]


def test_reply_failure_still_marks_posted_and_logs():
    store, client = FakeStore(due=[make_post(**LINK)]), FakeClient()
    original = client.post_text

    def flaky(text, reply_to=None):
        if reply_to:
            raise ThreadsError("1", "reply boom")
        return original(text, reply_to)

    client.post_text = flaky
    run(store, client)
    assert store.posted == [("TH-LIVING-20261101-001", "m1", None)]
    assert store.failures[0][1] == "reply"


def test_dry_run_makes_no_calls():
    store, client = FakeStore(due=[make_post()]), FakeClient()
    assert run(store, client, dry_run=True) == []
    assert client.calls == [] and store.posted == []


def test_token_expired_aborts():
    store, client = FakeStore(due=[make_post()]), FakeClient(fail_times=1, error_code="190")
    with pytest.raises(ThreadsError):
        run(store, client)
    assert len(client.calls) == 1


def test_no_quota_stops():
    store, client = FakeStore(due=[make_post()]), FakeClient(quota=0)
    assert run(store, client) == []
    assert client.calls == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/pipelines/test_publish.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipelines.threads_post.publish'`

- [ ] **Step 3: 구현**

`pipelines/threads_post/publish.py`:
```python
"""APPROVED + 예약시각 지난 Threads 글 게시 → 첫 댓글에 링크+대가성 문구."""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta

from channels.threads.client import TOKEN_EXPIRED, ThreadsError
from core.models import Post
from core.safety import blocking_problems, hold_reasons

MAX_RETRY = 2
RETRY_WAIT_SEC = 5


def reply_text(post: Post) -> str:
    return f"{post.link}\n\n{post.disclosure}"


def _with_retry(fn, sleep):
    for attempt in range(MAX_RETRY + 1):
        try:
            return fn()
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED or attempt == MAX_RETRY:
                raise
            sleep(RETRY_WAIT_SEC)


def run_publish(store, client, daily_cap: int, now: datetime, log: logging.Logger, *,
                dry_run: bool = False, sleep=time.sleep) -> list[str]:
    due = store.approved_threads_due(now)
    if not due:
        log.info("게시할 APPROVED 글 없음")
        return []
    recent = store.posted_threads_since(now - timedelta(days=1))
    quota = client.quota_left()
    done: list[str] = []

    for post in due:
        cid = post.content_id
        problems = blocking_problems(post)
        if problems:
            log.warning("%s 게시 불가: %s", cid, ", ".join(problems))
            store.mark_failed(post, ", ".join(problems))
            continue
        reasons = hold_reasons(post, recent, daily_cap, now)
        if reasons:
            log.info("%s 다음 실행으로 보류: %s", cid, ", ".join(reasons))
            continue
        if quota <= 0:
            log.warning("Threads 게시 한도 소진 — 이번 실행 중단")
            break
        if dry_run:
            log.info("[dry-run] 게시 예정: %s", cid)
            continue

        try:
            media_id = _with_retry(lambda: client.post_text(post.text), sleep)
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                raise
            log.error("%s 게시 실패: %s", cid, e)
            store.mark_failed(post, f"post: {e}")
            store.log_failure(cid, "post", e.code, e.message, MAX_RETRY, "FAILED", now)
            continue

        reply_id = None
        if post.link:
            try:
                reply_id = _with_retry(lambda: client.post_text(reply_text(post), reply_to=media_id), sleep)
            except ThreadsError as e:
                if e.code == TOKEN_EXPIRED:
                    store.mark_posted(post, media_id, None, now)
                    raise
                log.error("%s 링크 댓글 실패 (본문은 게시됨): %s", cid, e)
                store.log_failure(cid, "reply", e.code, e.message, MAX_RETRY, "POSTED_NO_REPLY", now)

        store.mark_posted(post, media_id, reply_id, now)
        recent.append(replace(post, posted_at=now, media_id=media_id))
        quota -= 1
        done.append(cid)
        log.info("%s 게시 완료", cid)
    return done
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/pipelines/test_publish.py -v`
Expected: 11 passed

- [ ] **Step 5: 커밋**

```bash
git add pipelines/threads_post/publish.py tests/pipelines/test_publish.py
git commit -m "feat(threads_post): APPROVED 글 게시와 링크 댓글, 재시도·보류 규칙"
```

---

### Task 8: 인사이트 수집 파이프라인

**Files:**
- Create: `pipelines/threads_post/collect.py`
- Test: `tests/pipelines/test_collect.py`

**Interfaces:**
- Consumes: `store.posted_threads_since`, `add_metrics`, `mark_collected`, `log_failure`, `client.insights`, `ThreadsError`, `TOKEN_EXPIRED`
- Produces: `MILESTONES = (24, 72, 168)`, `run_collect(store, client, now: datetime, log: logging.Logger) -> int` (기록한 행 수)

규칙: 하루 2회 실행이라 정확한 시점을 못 맞춘다. 지난 마일스톤 중 **가장 큰 것 하나만** 기록하고(실제 경과 시간 함께), 그보다 작은 미수집 마일스톤은 수집 완료로 표시한다.

- [ ] **Step 1: 실패 테스트 작성**

`tests/pipelines/test_collect.py`:
```python
import logging
from datetime import datetime, timedelta

from core.models import KST
from fakes import FakeClient, FakeStore, make_post
from pipelines.threads_post.collect import run_collect

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=KST)
LOG = logging.getLogger("moruu")


def posted(hours_ago, collected=frozenset()):
    return make_post(posted_at=NOW - timedelta(hours=hours_ago), media_id="m1", collected=frozenset(collected))


def test_collects_24h_milestone():
    store, client = FakeStore(recent=[posted(30)]), FakeClient(insights={"views": 120})
    assert run_collect(store, client, NOW, LOG) == 1
    assert store.metrics == [("TH-LIVING-20261101-001", 24, 30.0, {"views": 120})]
    assert store.collected == [("TH-LIVING-20261101-001", [24])]


def test_missed_milestones_record_largest_only():
    store, client = FakeStore(recent=[posted(80)]), FakeClient()
    run_collect(store, client, NOW, LOG)
    assert [m[1] for m in store.metrics] == [72]
    assert store.collected == [("TH-LIVING-20261101-001", [24, 72])]


def test_already_collected_is_skipped():
    store, client = FakeStore(recent=[posted(30, {24})]), FakeClient()
    assert run_collect(store, client, NOW, LOG) == 0
    assert client.calls == []


def test_too_early_is_skipped():
    store, client = FakeStore(recent=[posted(10)]), FakeClient()
    assert run_collect(store, client, NOW, LOG) == 0


def test_insight_error_is_logged_and_continues():
    store = FakeStore(recent=[posted(30), make_post(content_id="B", page_id="p2", posted_at=NOW - timedelta(hours=30), media_id="m2")])
    client = FakeClient(fail_times=1)
    assert run_collect(store, client, NOW, LOG) == 1
    assert store.failures[0][1] == "insight"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/pipelines/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipelines.threads_post.collect'`

- [ ] **Step 3: 구현**

`pipelines/threads_post/collect.py`:
```python
"""게시 후 24h / 72h / 7d 인사이트 → Notion 성과 DB."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from channels.threads.client import TOKEN_EXPIRED, ThreadsError

MILESTONES = (24, 72, 168)


def run_collect(store, client, now: datetime, log: logging.Logger) -> int:
    posts = store.posted_threads_since(now - timedelta(hours=MILESTONES[-1] + 48))
    written = 0
    for post in posts:
        if not post.media_id or not post.posted_at:
            continue
        elapsed = (now - post.posted_at).total_seconds() / 3600
        due = [h for h in MILESTONES if h not in post.collected and elapsed >= h]
        if not due:
            continue
        hours = max(due)
        try:
            metrics = client.insights(post.media_id)
        except ThreadsError as e:
            if e.code == TOKEN_EXPIRED:
                raise
            log.error("%s 인사이트 실패: %s", post.content_id, e)
            store.log_failure(post.content_id, "insight", e.code, e.message, 0, "SKIPPED", now)
            continue
        store.add_metrics(post, hours, round(elapsed, 1), metrics, now)
        store.mark_collected(post, due)
        written += 1
        log.info("%s %dh 인사이트 기록 (실제 %.1fh)", post.content_id, hours, elapsed)
    return written
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/pipelines -v`
Expected: 16 passed

- [ ] **Step 5: 커밋**

```bash
git add pipelines/threads_post/collect.py tests/pipelines/test_collect.py
git commit -m "feat(threads_post): 24h/72h/7d 인사이트 수집"
```

---

### Task 9: Notion DB 생성 + Integration 연결 (사람 + Claude 대화형)

> 서브에이전트가 아니라 **메인 세션에서 사용자와 함께** 진행. Notion MCP OAuth와 Integration 토큰 발급은 사용자가 직접 해야 함.

**Files:**
- Create: `docs/notion-schema.md`
- Modify: `.env` (NOTION_* 값 — 사용자가 직접 붙여넣기, Claude는 값을 보지 않음)

**Interfaces:**
- Consumes: `core/schema.py` 의 속성 이름 (정확히 같아야 함)
- Produces: Notion DB 3개 ID → `.env` 의 `NOTION_DB_CONTENT`, `NOTION_DB_METRICS`, `NOTION_DB_FAILURES`

- [ ] **Step 1: Notion MCP 연결 (사용자)**

```bash
claude mcp add --transport http --scope project notion https://mcp.notion.com/mcp
```
Claude Code에서 `/mcp` → notion → OAuth 완료

- [ ] **Step 2: Claude가 MCP로 부모 페이지 `moruu 운영` + DB 3개 생성**

**콘텐츠** (`content_id` 가 제목 속성)
| 속성 | 타입 | 옵션 |
|---|---|---|
| content_id | title | |
| 채널 | select | Threads, YT-쇼핑, YT-드라마 |
| 역할 | select | 인지, 브릿지, 수익 |
| 본문 | rich_text | |
| 링크 | url | |
| 대가성문구 | rich_text | |
| status | select | DRAFT, APPROVED, POSTED, FAILED |
| 예약시각 | date (시간 포함) | |
| 게시시각 | date | |
| 게시ID | rich_text | |
| 댓글ID | rich_text | |
| 오류 | rich_text | |
| 수집_24h / 수집_72h / 수집_7d | checkbox | |

**성과**
| 속성 | 타입 |
|---|---|
| 기록 | title |
| content_id | rich_text |
| 경과 | select (24h, 72h, 7d) |
| 실제경과h | number |
| 조회 / 좋아요 / 댓글 / 리포스트 / 인용 | number |
| 수집시각 | date |

**실패 로그**
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

> 상품·소재 은행·일별 지표·정산·비용·작업시간·리포트 DB는 이 계획 범위 밖 (Step 2.5 / Step 3 계획에서 생성).

- [ ] **Step 3: `docs/notion-schema.md` 작성** — 위 표 3개 + 각 DB의 URL/ID (ID는 비밀 아님) + "속성 이름은 core/schema.py 와 같이 바꾼다"

- [ ] **Step 4: Internal Integration (사용자)**
1. https://www.notion.so/profile/integrations → 새 API 통합 → 이름 `moruu-bot`, 해당 워크스페이스
2. 기능: 콘텐츠 읽기·업데이트·삽입
3. 시크릿 복사 → `.env` 의 `NOTION_TOKEN=` 에 직접 붙여넣기
4. `moruu 운영` 페이지 → `···` → 연결 → `moruu-bot` 추가 (하위 DB 3개에 상속)
5. DB ID 3개를 `.env` 에 기입

- [ ] **Step 5: 연결 확인 (값 출력 없이)**

Run: `uv run python -c "from dotenv import load_dotenv; import os; load_dotenv(); from core.config import Settings; Settings.from_env(os.environ); print('ok')"`
Expected: `ok`

- [ ] **Step 6: 커밋**

```bash
git add docs/notion-schema.md
git commit -m "docs: Notion DB 스키마와 ID 기록"
```

---

### Task 10: CLI + 실제 연결 시험

**Files:**
- Create: `pipelines/threads_post/__main__.py`

**Interfaces:**
- Consumes: `Settings`, `setup_logging`, `NotionStore`, `DbIds`, `ThreadsClient`, `needs_refresh`, `persist_token`, `run_publish`, `run_collect`, `TOKEN_EXPIRED`, `ThreadsError`
- Produces: `uv run python -m pipelines.threads_post [--dry-run] [--only publish|collect|all]`, 종료 코드 0 정상 / 1 설정 오류 / 2 토큰 만료

- [ ] **Step 1: 구현**

`pipelines/threads_post/__main__.py`:
```python
"""python -m pipelines.threads_post [--dry-run] [--only publish|collect|all]"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from channels.threads.client import TOKEN_EXPIRED, ThreadsClient, ThreadsError
from channels.threads.token import needs_refresh, persist_token
from core.config import ConfigError, Settings
from core.log import setup_logging
from core.models import KST
from core.notion_store import DbIds, NotionStore
from pipelines.threads_post.collect import run_collect
from pipelines.threads_post.publish import run_publish

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="threads_post")
    ap.add_argument("--dry-run", action="store_true", help="게시하지 않고 대상만 출력")
    ap.add_argument("--only", choices=["publish", "collect", "all"], default="all")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        s = Settings.from_env(os.environ)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    log = setup_logging([s.threads_token, s.notion_token])
    now = datetime.now(KST)

    token = s.threads_token
    if not args.dry_run and needs_refresh(s.threads_token_issued, now.date()):
        token, _ = ThreadsClient(s.threads_user_id, token).refresh_token()
        persist_token(token, now.date(), env_path=ROOT / ".env", environ=os.environ)
        log = setup_logging([token, s.threads_token, s.notion_token])
        log.info("Threads 토큰 갱신 완료")

    client = ThreadsClient(s.threads_user_id, token)
    store = NotionStore(s.notion_token, DbIds(s.notion_db_content, s.notion_db_metrics, s.notion_db_failures))
    try:
        if args.only in ("publish", "all"):
            run_publish(store, client, s.daily_cap, now, log, dry_run=args.dry_run)
        if args.only in ("collect", "all") and not args.dry_run:
            run_collect(store, client, now, log)
    except ThreadsError as e:
        if e.code == TOKEN_EXPIRED:
            log.error("Threads 토큰 만료 — uv run python -m channels.threads.get_token 으로 재발급 필요")
            return 2
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 전체 테스트**

Run: `uv run pytest -v`
Expected: 전부 PASS (smoke 1 + core 21 + channels 14 + pipelines 16 = 52)

- [ ] **Step 3: dry-run (빈 DB)**

Run: `uv run python -m pipelines.threads_post --dry-run`
Expected: `게시할 APPROVED 글 없음`, 종료 코드 0, 토큰 문자열 출력 없음

- [ ] **Step 4: 실제 게시 1회 (사용자 확인 후)**

1. 사용자가 Notion 콘텐츠 DB에 시험 글 1개: 채널 Threads, 역할 인지, 본문 짧게, 링크 없음, 예약시각 = 지금, status = APPROVED
2. `uv run python -m pipelines.threads_post --dry-run` → `[dry-run] 게시 예정: <content_id>`
3. 사용자 OK 후 `uv run python -m pipelines.threads_post --only publish`
4. 확인: Threads 앱에 글 게시됨, Notion status=POSTED, 게시ID·게시시각 채워짐
5. 시험 글은 사용자가 Threads에서 직접 삭제할지 결정

- [ ] **Step 5: 커밋**

```bash
git add pipelines/threads_post/__main__.py
git commit -m "feat(threads_post): CLI (dry-run, 토큰 자동 갱신, 종료 코드)"
```

---

### Task 11: GitHub Actions (사람 + Claude)

**Files:**
- Create: `.github/workflows/threads.yml`

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/threads.yml`:
```yaml
name: threads

on:
  schedule:
    - cron: "0 23 * * *"   # KST 08:00
    - cron: "0 11 * * *"   # KST 20:00
  workflow_dispatch:
    inputs:
      only:
        description: "publish / collect / all"
        default: all
        type: choice
        options: [all, publish, collect]
      dry_run:
        description: "게시하지 않고 대상만 확인"
        default: false
        type: boolean

concurrency:
  group: threads
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pytest -q
      - name: threads_post
        env:
          THREADS_USER_ID: ${{ secrets.THREADS_USER_ID }}
          THREADS_ACCESS_TOKEN: ${{ secrets.THREADS_ACCESS_TOKEN }}
          THREADS_TOKEN_ISSUED: ${{ secrets.THREADS_TOKEN_ISSUED }}
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_DB_CONTENT: ${{ secrets.NOTION_DB_CONTENT }}
          NOTION_DB_METRICS: ${{ secrets.NOTION_DB_METRICS }}
          NOTION_DB_FAILURES: ${{ secrets.NOTION_DB_FAILURES }}
          MORUU_DAILY_CAP: "3"
          GH_PAT: ${{ secrets.GH_PAT }}
        run: |
          ARGS="--only ${{ inputs.only || 'all' }}"
          if [ "${{ inputs.dry_run }}" = "true" ]; then ARGS="$ARGS --dry-run"; fi
          uv run python -m pipelines.threads_post $ARGS
```

- [ ] **Step 2: GitHub 비공개 레포 생성 + push (사용자 확인 후)**

```bash
gh repo create moruu --private --source . --remote origin
git push -u origin feat/threads-semi-auto
```
PR 생성 → main 병합 (예약 실행은 기본 브랜치의 워크플로만 동작)

- [ ] **Step 3: Secrets 등록 (사용자가 직접 — 값이 대화에 남지 않게)**

로컬 `.env` 에서 바로 올리기:
```bash
for k in THREADS_USER_ID THREADS_ACCESS_TOKEN THREADS_TOKEN_ISSUED NOTION_TOKEN NOTION_DB_CONTENT NOTION_DB_METRICS NOTION_DB_FAILURES; do
  grep "^$k=" .env | cut -d= -f2- | tr -d '\r' | gh secret set "$k"
done
```

- [ ] **Step 4: 토큰 갱신용 PAT (사용자)**

GitHub → Settings → Developer settings → Fine-grained tokens → 저장소 `moruu`만, 권한 **Secrets: Read and write** → 만료 1년 → `gh secret set GH_PAT` 로 등록 (만료일 캘린더에 기록)

- [ ] **Step 5: 수동 실행 확인**

Actions → threads → Run workflow → `dry_run` 체크 → 성공(초록) + 로그에 토큰 없음 확인. 이후 `dry_run` 해제 실행.

- [ ] **Step 6: 커밋**

```bash
git add .github/workflows/threads.yml
git commit -m "ci: Threads 게시·수집 워크플로 (하루 2회 + 수동)"
git push
```

> 운영 전제 (PLAN.md Step 2): 자동 예약 실행은 병합 즉시 켜지지만, **수동 게시 30개 전에는 콘텐츠를 APPROVED로 바꾸지 않는 것**으로 실질적으로 꺼둔다.
