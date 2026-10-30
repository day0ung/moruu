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


def test_shorts_settings_needs_only_notion_and_tts():
    from core.config import ShortsSettings
    env = {k: FULL[k] for k in ("NOTION_TOKEN", "NOTION_DB_CONTENT", "NOTION_DB_METRICS", "NOTION_DB_FAILURES")}
    s = ShortsSettings.from_env({**env, "GOOGLE_TTS_API_KEY": "gk", "TTS_RATE": "1.1"})
    assert (s.tts_key, s.tts_rate, s.tts_voice) == ("gk", 1.1, "ko-KR-Neural2-A")
    assert (s.tts_voice_male, s.lexicon_page) == ("ko-KR-Neural2-C", "")
    s2 = ShortsSettings.from_env({**env, "GOOGLE_TTS_API_KEY": "gk", "TTS_VOICE_MALE": "m", "NOTION_PAGE_LEXICON": "lx"})
    assert (s2.tts_voice_male, s2.lexicon_page) == ("m", "lx")
    with pytest.raises(ConfigError) as e:
        ShortsSettings.from_env(env)
    assert "GOOGLE_TTS_API_KEY" in str(e.value)
    assert ShortsSettings.from_env(env, need_tts=False).tts_key == ""


def test_drama_settings_from_env():
    from core.config import DramaSettings

    env = {"NOTION_TOKEN": "t", "NOTION_DB_CONTENT": "c", "NOTION_DB_METRICS": "m", "NOTION_DB_FAILURES": "f",
           "GOOGLE_TTS_API_KEY": "k", "TTS_RATE": "1.1", "NOTION_PAGE_LEXICON": "lex"}
    s = DramaSettings.from_env(env)
    assert (s.tts_key, s.tts_rate, s.lexicon_page) == ("k", 1.1, "lex")
    no_key = {k: v for k, v in env.items() if k != "GOOGLE_TTS_API_KEY"}
    assert DramaSettings.from_env(no_key, need_tts=False).tts_key == ""
    with pytest.raises(ConfigError):
        DramaSettings.from_env(no_key)


def test_drive_and_telegram_settings_all_or_none():
    from core.config import DriveSettings, TelegramSettings

    env = {"GDRIVE_CLIENT_ID": "a", "GDRIVE_CLIENT_SECRET": "b", "GDRIVE_REFRESH_TOKEN": "c", "GDRIVE_ROOT_ID": "d"}
    assert DriveSettings.from_env(env) == DriveSettings("a", "b", "c", "d")
    assert DriveSettings.from_env({**env, "GDRIVE_ROOT_ID": ""}) is None
    assert TelegramSettings.from_env({"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}) == TelegramSettings("t", "1")
    assert TelegramSettings.from_env({"TELEGRAM_BOT_TOKEN": "t"}) is None
