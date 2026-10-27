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
