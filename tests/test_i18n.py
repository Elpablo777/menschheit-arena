from __future__ import annotations

from menschheit.i18n import catalog, normalize_lang, t, validate_catalogs


def test_catalogs_have_identical_keys() -> None:
    assert validate_catalogs() == []


def test_catalogs_are_non_trivial() -> None:
    assert len(catalog("de")) > 200
    assert len(catalog("en")) > 200


def test_normalize_lang() -> None:
    assert normalize_lang("de-DE") == "de"
    assert normalize_lang("EN_us") == "en"
    assert normalize_lang("fr") == "de"
    assert normalize_lang(None) == "de"


def test_translation_fallback() -> None:
    assert t("app.name", "en") == "Menschheit Arena"
    assert t("does.not.exist", "en") == "does.not.exist"
    assert "Debatten" in t("hero.kicker", "de")
