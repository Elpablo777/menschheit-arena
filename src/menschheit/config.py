"""Zentrale Konfiguration, ausschliesslich aus Umgebungsvariablen."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "ja"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or not value.strip() else value.strip()


def _absolute_sqlite(url: str) -> str:
    """Relative SQLite-Pfade immer relativ zum Projektwurzelverzeichnis aufloesen."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix) :]
    if not path or path.startswith(":memory:"):
        return url
    if path.startswith("/") or (len(path) > 2 and path[1] == ":"):
        return url
    return prefix + (PROJECT_ROOT / path).resolve().as_posix()


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "mock": {
        "label": "Demo (ohne API-Key)",
        "base_url": "",
        "pro": "mock-pro",
        "contra": "mock-contra",
        "judge": "mock-judge",
        "moderator": "mock-moderator",
    },
    "openrouter": {
        "label": "OpenRouter (viele Modelle, ein Key)",
        "base_url": "https://openrouter.ai/api/v1",
        "pro": "anthropic/claude-sonnet-4",
        "contra": "deepseek/deepseek-r1",
        "judge": "openai/gpt-4o",
        "moderator": "google/gemini-2.5-flash",
    },
    "deepseek": {
        "label": "DeepSeek (direkte API)",
        "base_url": "https://api.deepseek.com/v1",
        "pro": "deepseek-chat",
        "contra": "deepseek-reasoner",
        "judge": "deepseek-chat",
        "moderator": "deepseek-chat",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "pro": "gpt-4.1",
        "contra": "gpt-4.1-mini",
        "judge": "gpt-4.1",
        "moderator": "gpt-4.1-mini",
    },
    "mistral": {
        "label": "Mistral (EU-Endpunkt, AVV pruefen)",
        "base_url": "https://api.mistral.ai/v1",
        "pro": "mistral-large-latest",
        "contra": "mistral-small-latest",
        "judge": "mistral-large-latest",
        "moderator": "mistral-small-latest",
    },
    "ollama": {
        "label": "Ollama (lokal, kein Cloud-Transfer)",
        "base_url": "http://127.0.0.1:11434/v1",
        "pro": "llama3.1",
        "contra": "qwen2.5",
        "judge": "llama3.1",
        "moderator": "llama3.1",
    },
    "litellm": {
        "label": "LiteLLM Proxy (self-hosted)",
        "base_url": "http://127.0.0.1:4000/v1",
        "pro": "arena-pro-model",
        "contra": "arena-contra-model",
        "judge": "arena-judge-model",
        "moderator": "arena-pro-model",
    },
    "openai_compat": {
        "label": "Beliebiger OpenAI-kompatibler Endpunkt",
        "base_url": "https://example.invalid/v1",
        "pro": "pro-model",
        "contra": "contra-model",
        "judge": "judge-model",
        "moderator": "moderator-model",
    },
}


@dataclass(slots=True)
class Settings:
    app_name: str = "Menschheit Arena"
    version: str = "0.1.0"
    env: str = "local"
    lang: str = "de"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite:///./data/menschheit.db"
    access_token: str = ""

    provider: str = "mock"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 1400
    timeout_seconds: float = 90.0

    pro_model: str = "mock-pro"
    contra_model: str = "mock-contra"
    judge_model: str = "mock-judge"
    moderator_model: str = "mock-moderator"

    default_rounds: int = 4
    max_rounds: int = 8
    word_limit: int = 350

    pentest_execution_enabled: bool = False
    allow_public_targets: bool = False

    allowed_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        provider = _str("LLM_PROVIDER", "mock").lower()
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["mock"])
        return cls(
            env=_str("APP_ENV", "local"),
            lang=_str("APP_LANG", "de").lower(),
            host=_str("HOST", "127.0.0.1"),
            port=_int("PORT", 8000),
            database_url=_absolute_sqlite(_str("DATABASE_URL", "sqlite:///./data/menschheit.db")),
            access_token=_str("APP_ACCESS_TOKEN", ""),
            provider=provider,
            llm_base_url=_str("LLM_BASE_URL", preset["base_url"]),
            llm_api_key=_str("LLM_API_KEY", ""),
            temperature=_float("LLM_TEMPERATURE", 0.7),
            max_tokens=_int("LLM_MAX_TOKENS", 1400),
            timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 90.0),
            pro_model=_str("ARENA_PRO_MODEL", preset["pro"]),
            contra_model=_str("ARENA_CONTRA_MODEL", preset["contra"]),
            judge_model=_str("ARENA_JUDGE_MODEL", preset["judge"]),
            moderator_model=_str("ARENA_MODERATOR_MODEL", preset["moderator"]),
            default_rounds=max(1, _int("ARENA_DEFAULT_ROUNDS", 4)),
            max_rounds=max(1, _int("ARENA_MAX_ROUNDS", 8)),
            word_limit=max(100, _int("ARENA_WORD_LIMIT", 350)),
            pentest_execution_enabled=_bool("PENTEST_EXECUTION_ENABLED", False),
            allow_public_targets=_bool("ALLOW_PUBLIC_TARGETS", False),
        )

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock" or not self.llm_base_url

    def public_dict(self) -> dict[str, object]:
        """Nur unkritische Werte fuer die Oberflaeche."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "env": self.env,
            "lang": self.lang,
            "provider": self.provider,
            "provider_label": PROVIDER_PRESETS.get(self.provider, {}).get("label", self.provider),
            "models": {
                "pro": self.pro_model,
                "contra": self.contra_model,
                "judge": self.judge_model,
                "moderator": self.moderator_model,
            },
            "default_rounds": self.default_rounds,
            "max_rounds": self.max_rounds,
            "mock": self.is_mock,
            "pentest_execution_enabled": self.pentest_execution_enabled,
            "allow_public_targets": self.allow_public_targets,
            "api_docs": "/docs",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reload_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    get_settings.cache_clear()
    return get_settings()
