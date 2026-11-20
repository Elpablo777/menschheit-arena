"""Kleine, dateibasierte i18n-Schicht fuer Backend, UI und Berichte."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

SUPPORTED = ("de", "en")
FALLBACK = "de"


def normalize_lang(value: str | None) -> str:
    if not value:
        return FALLBACK
    short = value.strip().lower().split("-")[0].split("_")[0]
    return short if short in SUPPORTED else FALLBACK


@lru_cache(maxsize=8)
def catalog(lang: str) -> dict[str, str]:
    lang = normalize_lang(lang)
    path = resources.files("menschheit.i18n").joinpath(f"{lang}.json")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"i18n catalog {lang} is not an object")
    return {str(key): str(value) for key, value in data.items()}


def t(key: str, lang: str = FALLBACK, **kwargs: object) -> str:
    lang = normalize_lang(lang)
    text = catalog(lang).get(key) or catalog(FALLBACK).get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def both(key: str) -> dict[str, str]:
    return {lang: t(key, lang) for lang in SUPPORTED}


def validate_catalogs() -> list[str]:
    """Gibt fehlende oder zusaetzliche Schluessel zurueck (fuer Tests/Doctor)."""
    de = set(catalog("de"))
    en = set(catalog("en"))
    problems: list[str] = []
    if de - en:
        problems.append("missing in en: " + ", ".join(sorted(de - en)))
    if en - de:
        problems.append("missing in de: " + ", ".join(sorted(en - de)))
    return problems
