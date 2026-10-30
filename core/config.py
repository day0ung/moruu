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


SHORTS_REQUIRED = ("NOTION_TOKEN", "NOTION_DB_CONTENT", "NOTION_DB_METRICS", "NOTION_DB_FAILURES")


@dataclass(frozen=True)
class ShortsSettings:
    """쇼츠 렌더용 — Threads 키 없이 Notion + TTS 만."""
    notion_token: str
    notion_db_content: str
    notion_db_metrics: str
    notion_db_failures: str
    tts_key: str
    tts_voice: str = "ko-KR-Neural2-A"  # 여
    tts_voice_male: str = "ko-KR-Neural2-C"
    tts_rate: float = 1.0
    lexicon_page: str = ""  # 발음 사전 Notion 페이지 ID (없으면 사전 없이)

    @classmethod
    def from_env(cls, env: Mapping[str, str], need_tts: bool = True) -> ShortsSettings:
        """need_tts=False: --dry-run (파싱·검사만) 은 TTS 키 없이도 돈다."""
        required = SHORTS_REQUIRED + (("GOOGLE_TTS_API_KEY",) if need_tts else ())
        missing = [k for k in required if not env.get(k)]
        if missing:
            raise ConfigError("환경변수 없음: " + ", ".join(missing))
        return cls(
            notion_token=env["NOTION_TOKEN"],
            notion_db_content=env["NOTION_DB_CONTENT"],
            notion_db_metrics=env["NOTION_DB_METRICS"],
            notion_db_failures=env["NOTION_DB_FAILURES"],
            tts_key=env.get("GOOGLE_TTS_API_KEY", ""),
            tts_voice=env.get("TTS_VOICE") or "ko-KR-Neural2-A",
            tts_voice_male=env.get("TTS_VOICE_MALE") or "ko-KR-Neural2-C",
            tts_rate=float(env.get("TTS_RATE") or 1.0),
            lexicon_page=env.get("NOTION_PAGE_LEXICON", ""),
        )


@dataclass(frozen=True)
class DramaSettings:
    """드라마 렌더용 — 목소리는 시리즈 바이블에서, 여기엔 Notion + TTS 키만."""
    notion_token: str
    notion_db_content: str
    notion_db_metrics: str
    notion_db_failures: str
    tts_key: str
    tts_rate: float = 1.0  # 바이블 빠르기가 비었을 때
    lexicon_page: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str], need_tts: bool = True) -> DramaSettings:
        required = SHORTS_REQUIRED + (("GOOGLE_TTS_API_KEY",) if need_tts else ())
        missing = [k for k in required if not env.get(k)]
        if missing:
            raise ConfigError("환경변수 없음: " + ", ".join(missing))
        return cls(
            notion_token=env["NOTION_TOKEN"],
            notion_db_content=env["NOTION_DB_CONTENT"],
            notion_db_metrics=env["NOTION_DB_METRICS"],
            notion_db_failures=env["NOTION_DB_FAILURES"],
            tts_key=env.get("GOOGLE_TTS_API_KEY", ""),
            tts_rate=float(env.get("TTS_RATE") or 1.0),
            lexicon_page=env.get("NOTION_PAGE_LEXICON", ""),
        )


@dataclass(frozen=True)
class DriveSettings:
    """Drive 자료·결과 (넷 다 있어야 켜짐)."""
    client_id: str
    client_secret: str
    refresh_token: str
    root_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> DriveSettings | None:
        keys = ("GDRIVE_CLIENT_ID", "GDRIVE_CLIENT_SECRET", "GDRIVE_REFRESH_TOKEN", "GDRIVE_ROOT_ID")
        values = [env.get(k, "") for k in keys]
        return cls(*values) if all(values) else None


@dataclass(frozen=True)
class TelegramSettings:
    """텔레그램 알림 (둘 다 있어야 켜짐)."""
    token: str
    chat_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> TelegramSettings | None:
        token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")
        return cls(token, chat) if token and chat else None
