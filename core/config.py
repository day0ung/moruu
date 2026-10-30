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


LLM_DEFAULTS = {
    # 서비스: (주소, 키 환경변수, 역할별 기본 모델) — docs/research/free-llm-compare.md
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
               {"plan": "gemini-3.8-flash", "write": "gemini-3.8-flash", "review": "gemini-3.8-flash",
                "light": "gemini-3.5-flash-lite"}),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                   {r: "google/gemma-4-31b-it:free" for r in ("plan", "write", "review", "light")}),
}


@dataclass(frozen=True)
class LLMSettings:
    """대본 AI. LLM_PROVIDERS=gemini,openrouter 순서로 시도. 모델은 {서비스}_MODEL_{역할} 로 덮어쓴다."""
    providers: list

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LLMSettings:
        from channels.llm.client import Provider

        names = [n.strip() for n in (env.get("LLM_PROVIDERS") or "gemini,openrouter").split(",") if n.strip()]
        providers = []
        for name in names:
            if name not in LLM_DEFAULTS:
                raise ConfigError(f"모르는 AI 서비스: {name}")
            url, key_env, models = LLM_DEFAULTS[name]
            if not env.get(key_env):
                continue
            models = {role: env.get(f"{name.upper()}_MODEL_{role.upper()}") or m for role, m in models.items()}
            providers.append(Provider(name, url, env[key_env], models))
        return cls(providers)
