"""Provider-Katalog: bekannt oder frei konfiguriert."""

from __future__ import annotations

from typing import Any

# Modelle mit :free-Suffix auf OpenRouter. Stand: 2026-11.
# Die Liste ist eine Startauswahl, keine Garantie - OpenRouter aendert sie regelmaessig.
OPENROUTER_FREE: tuple[dict[str, str], ...] = (
    {"id": "deepseek/deepseek-r1:free", "label": "DeepSeek R1 (Reasoning, kostenlos)"},
    {"id": "deepseek/deepseek-chat-v3-0324:free", "label": "DeepSeek V3 (kostenlos)"},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B Instruct (kostenlos)"},
    {"id": "meta-llama/llama-3.1-8b-instruct:free", "label": "Llama 3.1 8B Instruct (kostenlos)"},
    {"id": "qwen/qwen3-235b-a22b:free", "label": "Qwen3 235B (kostenlos)"},
    {"id": "google/gemma-3-27b-it:free", "label": "Gemma 3 27B (kostenlos)"},
    {"id": "mistralai/mistral-small-3.2-24b-instruct:free", "label": "Mistral Small 3.2 (kostenlos)"},
    {"id": "nousresearch/hermes-3-llama-3.1-405b:free", "label": "Hermes 3 405B (kostenlos)"},
)

# Kompakte Startauswahl fuer die haeufigsten Anbieter.
PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "id": "openrouter",
        "label": "OpenRouter",
        "label_de": "OpenRouter (kostenlose Modelle moeglich)",
        "label_en": "OpenRouter (free models available)",
        "group": "cloud",
        "base_url": "https://openrouter.ai/api/v1",
        "docs": "https://openrouter.ai/models?max_price=0",
        "key_url": "https://openrouter.ai/keys",
        "models": [
            {"id": model["id"], "label": model["label"]}
            for model in OPENROUTER_FREE
        ],
        "defaults": {
            "pro": OPENROUTER_FREE[0]["id"],
            "contra": OPENROUTER_FREE[1]["id"],
            "judge": OPENROUTER_FREE[2]["id"],
            "moderator": OPENROUTER_FREE[2]["id"],
        },
        "notes_de": "Kostenlose Modelle tragen das Suffix :free. Rate-Limits sind strenger.",
        "notes_en": "Free models carry the :free suffix. Rate limits are tighter.",
    },
    "deepseek": {
        "id": "deepseek",
        "label": "DeepSeek",
        "label_de": "DeepSeek (Direktanbieter)",
        "label_en": "DeepSeek (direct)",
        "group": "cloud",
        "base_url": "https://api.deepseek.com/v1",
        "docs": "https://api-docs.deepseek.com",
        "key_url": "https://platform.deepseek.com",
        "models": [
            {"id": "deepseek-chat", "label": "deepseek-chat"},
            {"id": "deepseek-reasoner", "label": "deepseek-reasoner (Reasoning)"},
        ],
        "defaults": {
            "pro": "deepseek-chat",
            "contra": "deepseek-chat",
            "judge": "deepseek-chat",
            "moderator": "deepseek-chat",
        },
        "notes_de": "Guenstiger Anbieter, gute Reasoning-Modelle.",
        "notes_en": "Cheap provider, strong reasoning models.",
    },
    "openai": {
        "id": "openai",
        "label": "OpenAI",
        "label_de": "OpenAI",
        "label_en": "OpenAI",
        "group": "cloud",
        "base_url": "https://api.openai.com/v1",
        "docs": "https://platform.openai.com/docs",
        "key_url": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4.1-mini", "label": "gpt-4.1-mini"},
            {"id": "gpt-4.1", "label": "gpt-4.1"},
            {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
        ],
        "defaults": {
            "pro": "gpt-4.1",
            "contra": "gpt-4.1-mini",
            "judge": "gpt-4.1",
            "moderator": "gpt-4.1-mini",
        },
        "notes_de": "Bezahlt, zuverlaessig.",
        "notes_en": "Paid, reliable.",
    },
    "mistral": {
        "id": "mistral",
        "label": "Mistral",
        "label_de": "Mistral (EU-Anbieter)",
        "label_en": "Mistral (EU provider)",
        "group": "cloud",
        "base_url": "https://api.mistral.ai/v1",
        "docs": "https://docs.mistral.ai",
        "key_url": "https://console.mistral.ai",
        "models": [
            {"id": "mistral-small-latest", "label": "mistral-small-latest"},
            {"id": "mistral-large-latest", "label": "mistral-large-latest"},
        ],
        "defaults": {
            "pro": "mistral-large-latest",
            "contra": "mistral-small-latest",
            "judge": "mistral-large-latest",
            "moderator": "mistral-small-latest",
        },
        "notes_de": "EU-Endpunkt. AVV mit dem Anbieter klaeren.",
        "notes_en": "EU endpoint. Clarify the data processing agreement.",
    },
    "groq": {
        "id": "groq",
        "label": "Groq",
        "label_de": "Groq (schnell, kostenloses Kontingent)",
        "label_en": "Groq (fast, free tier)",
        "group": "cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "docs": "https://console.groq.com/docs",
        "key_url": "https://console.groq.com/keys",
        "models": [
            {"id": "llama-3.3-70b-versatile", "label": "llama-3.3-70b-versatile"},
            {"id": "llama-3.1-8b-instant", "label": "llama-3.1-8b-instant"},
        ],
        "defaults": {
            "pro": "llama-3.3-70b-versatile",
            "contra": "llama-3.1-8b-instant",
            "judge": "llama-3.3-70b-versatile",
            "moderator": "llama-3.1-8b-instant",
        },
        "notes_de": "Sehr schnell, grosses kostenloses Kontingent.",
        "notes_en": "Very fast, generous free tier.",
    },
    "ollama": {
        "id": "ollama",
        "label": "Ollama",
        "label_de": "Ollama (lokal, kein Cloud-Transfer)",
        "label_en": "Ollama (local, no cloud transfer)",
        "group": "local",
        "base_url": "http://127.0.0.1:11434/v1",
        "docs": "https://ollama.com",
        "key_url": "",
        "models": [
            {"id": "llama3.1", "label": "llama3.1"},
            {"id": "qwen3", "label": "qwen3"},
            {"id": "mistral", "label": "mistral"},
        ],
        "defaults": {
            "pro": "llama3.1",
            "contra": "qwen3",
            "judge": "llama3.1",
            "moderator": "llama3.1",
        },
        "notes_de": "Laeuft auf dem eigenen Rechner. Kein API-Key noetig.",
        "notes_en": "Runs on your own machine. No API key needed.",
    },
    "litellm": {
        "id": "litellm",
        "label": "LiteLLM",
        "label_de": "LiteLLM Proxy (self-hosted)",
        "label_en": "LiteLLM proxy (self-hosted)",
        "group": "selfhosted",
        "base_url": "http://127.0.0.1:4000/v1",
        "docs": "https://docs.litellm.ai",
        "key_url": "",
        "models": [
            {"id": "arena-pro-model", "label": "arena-pro-model"},
            {"id": "arena-contra-model", "label": "arena-contra-model"},
        ],
        "defaults": {
            "pro": "arena-pro-model",
            "contra": "arena-contra-model",
            "judge": "arena-pro-model",
            "moderator": "arena-contra-model",
        },
        "notes_de": "Eigener Proxy, eigene Preis- und Routingregeln.",
        "notes_en": "Your own proxy, your own pricing and routing rules.",
    },
    "custom": {
        "id": "custom",
        "label": "Custom",
        "label_de": "Eigener Endpunkt (OpenAI-kompatibel)",
        "label_en": "Custom endpoint (OpenAI compatible)",
        "group": "custom",
        "base_url": "",
        "docs": "",
        "key_url": "",
        "models": [],
        "defaults": {"pro": "pro-model", "contra": "contra-model", "judge": "judge-model", "moderator": "moderator-model"},
        "notes_de": "Jede OpenAI-kompatible URL. Base-URL und Modellnamen selbst eintragen.",
        "notes_en": "Any OpenAI-compatible URL. Enter base URL and model names yourself.",
    },
    "mock": {
        "id": "mock",
        "label": "Demo",
        "label_de": "Demo (ohne API-Key, deterministisch)",
        "label_en": "Demo (no API key, deterministic)",
        "group": "local",
        "base_url": "",
        "docs": "",
        "key_url": "",
        "models": [],
        "defaults": {"pro": "mock-pro", "contra": "mock-contra", "judge": "mock-judge", "moderator": "mock-moderator"},
        "notes_de": "Lokale Antworten ohne Netzwerk. Fuer Tests und Konstruktionspruefung.",
        "notes_en": "Local responses without network. For tests and wiring checks.",
    },
}

# Reihenfolge im Dropdown: erst die grossen Anbieter, dann Local, dann Demo.
PROVIDER_ORDER: tuple[str, ...] = (
    "openrouter",
    "deepseek",
    "openai",
    "mistral",
    "groq",
    "ollama",
    "litellm",
    "custom",
    "mock",
)


def provider_ids() -> list[str]:
    return [pid for pid in PROVIDER_ORDER if pid in PROVIDERS] + [
        pid for pid in PROVIDERS if pid not in PROVIDER_ORDER
    ]


def provider_info(provider_id: str) -> dict[str, Any]:
    return dict(PROVIDERS.get(provider_id, PROVIDERS["mock"]))


def catalogue() -> list[dict[str, Any]]:
    """Oeffentliche Liste fuer UI und CLI."""
    items: list[dict[str, Any]] = []
    for pid in provider_ids():
        info = provider_info(pid)
        items.append(
            {
                "id": info["id"],
                "label": info["label"],
                "label_de": info.get("label_de") or info["label"],
                "label_en": info.get("label_en") or info["label"],
                "group": info.get("group", "cloud"),
                "base_url": info.get("base_url", ""),
                "docs": info.get("docs", ""),
                "key_url": info.get("key_url", ""),
                "models": [dict(model) for model in info.get("models", [])],
                "defaults": dict(info.get("defaults", {})),
                "notes_de": info.get("notes_de", ""),
                "notes_en": info.get("notes_en", ""),
                "needs_key": pid not in {"mock", "ollama", "litellm", "custom"},
            }
        )
    return items