"""API-Eingabeschemata mit strikter Validierung."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..i18n import normalize_lang

ROLES = ("pro", "contra", "judge", "moderator")

# Obergrenze bewusst hoch: lange Debatten sind ein legitimer Anwendungsfall.
MAX_ROUNDS_LIMIT = 2000


class DebateConfig(BaseModel):
    """Optionale Feineinstellungen pro Debatte."""

    model_config = ConfigDict(extra="forbid")

    word_limit: int | None = Field(default=None, ge=80, le=4000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=128, le=32000)
    provider: str | None = Field(default=None, max_length=60)
    base_url: str | None = Field(default=None, max_length=300)
    pro_model: str | None = Field(default=None, max_length=200)
    contra_model: str | None = Field(default=None, max_length=200)
    judge_model: str | None = Field(default=None, max_length=200)
    moderator_model: str | None = Field(default=None, max_length=200)
    early_stop: bool | None = Field(
        default=None,
        description="Bei True darf der Moderator die Debatte vorzeitig beenden.",
    )
    confidence_gate: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Konfidenzschwelle, ab der 'CONVINCED' akzeptiert wird. Standard 25.",
    )
    show_private_reasoning: bool | None = Field(
        default=None, description="Nur Anzeige: internes Reasoning im Protokoll zeigen."
    )

    @field_validator("provider", "base_url", "pro_model", "contra_model", "judge_model", "moderator_model")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DebateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=8, max_length=4000)
    rounds: int | None = Field(default=None, ge=1, le=MAX_ROUNDS_LIMIT)
    language: str = "de"
    models: dict[str, str] | None = None
    config: DebateConfig | None = None
    sync: bool = False
    parent_debate_id: str | None = Field(default=None, max_length=120)

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, value: object) -> str:
        return normalize_lang(str(value or "de"))

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 8:
            raise ValueError("Thema ist zu kurz.")
        return cleaned

    @field_validator("models")
    @classmethod
    def _models(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        cleaned: dict[str, str] = {}
        for role, model in value.items():
            if role not in ROLES:
                raise ValueError(f"Unbekannte Rolle: {role}")
            model = str(model).strip()
            if not model or len(model) > 200:
                raise ValueError(f"Ungueltiger Modellname fuer {role}")
            cleaned[role] = model
        return cleaned


class DebateFork(BaseModel):
    """Neue Debatte auf Basis einer bestehenden, mit anderem Thema."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=8, max_length=4000)
    rounds: int | None = Field(default=None, ge=1, le=MAX_ROUNDS_LIMIT)
    language: str | None = None
    inherit_models: bool = True
    inherit_config: bool = True

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 8:
            raise ValueError("Thema ist zu kurz.")
        return cleaned


class EngagementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(min_length=2, max_length=200)
    scope: list[str] = Field(min_length=1, max_length=50)
    ports: list[int] = Field(min_length=1, max_length=20)
    valid_from: str
    valid_until: str
    roe_text: str = Field(min_length=50, max_length=20000)
    authorized_by: str = Field(min_length=2, max_length=200)
    emergency_contact: str = Field(min_length=2, max_length=500)

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("Scope darf nicht leer sein.")
        return cleaned

    @field_validator("ports")
    @classmethod
    def _ports(cls, value: list[int]) -> list[int]:
        ports = sorted({int(port) for port in value})
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("Ports muessen zwischen 1 und 65535 liegen.")
        return ports


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver: str = Field(min_length=2, max_length=200)


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="human", max_length=200)
    reason: str = Field(default="", max_length=1000)


class KillSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="human", max_length=200)


class FindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=300)
    owasp_ref: str = Field(default="", max_length=120)
    cvss_vector: str = Field(default="", max_length=300)
    evidence: str = Field(min_length=10, max_length=20000)
    remediation: str = Field(min_length=10, max_length=20000)
    verified_by_human: bool = False
    actor: str = Field(default="human", max_length=200)


class ValidateTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1, max_length=2000)
    port: int | None = Field(default=None, ge=1, le=65535)
    scope: list[str] = Field(min_length=1, max_length=50)
    ports: list[int] = Field(default_factory=lambda: [80, 443], max_length=20)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["rules", "llm"] = "rules"
    language: str = "de"

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, value: object) -> str:
        return normalize_lang(str(value or "de"))


class ProviderTestRequest(BaseModel):
    """Testet einen Provider, ohne die globale Konfiguration zu veraendern."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(max_length=60)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=400)
    model: str | None = Field(default=None, max_length=200)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Provider fehlt.")
        return cleaned


class ProviderSelect(BaseModel):
    """Speichert einen Provider als Standard in .env (mit Backup)."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(max_length=60)
    base_url: str = Field(default="", max_length=400)
    api_key: str = Field(default="", max_length=600)
    model: str = Field(default="", max_length=200)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Provider fehlt.")
        return cleaned