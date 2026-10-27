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
