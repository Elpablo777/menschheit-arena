"""Auswahl des Providers anhand der Konfiguration."""

from __future__ import annotations

from ..config import Settings
from .base import LLMClient, LLMError
from .mock import MockLLM
from .openai_compat import OpenAICompatClient

ROLE_FIELDS = {
    "pro": "pro_model",
    "contra": "contra_model",
    "judge": "judge_model",
    "moderator": "moderator_model",
}


def model_for(settings: Settings, role: str) -> str:
    field = ROLE_FIELDS.get(role)
    if not field:
        raise LLMError(f"Unbekannte Rolle: {role}")
    return str(getattr(settings, field))


def build_client(settings: Settings) -> LLMClient:
    if settings.is_mock:
        return MockLLM()
    return OpenAICompatClient(
        settings.llm_base_url,
        settings.llm_api_key,
        timeout=settings.timeout_seconds,
        provider=settings.provider,
        default_temperature=settings.temperature,
        default_max_tokens=settings.max_tokens,
    )
