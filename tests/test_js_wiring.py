"""Prueft, dass app.js keine Funktionsnamen aufruft, die nirgends definiert sind."""

from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "src" / "menschheit" / "web" / "static" / "app.js"

# Methoden, eingebaute Objekte und JS-Sprachkonstrukte.
METHODS = {
    "add", "addEventListener", "all", "catch", "ceil", "charAt", "click", "cloneNode", "close",
    "closest", "contains", "createElement", "delete", "endsWith", "fill", "filter", "find",
    "findIndex", "floor", "focus", "forEach", "format", "from", "get", "getDate", "getElementById",
    "getItem", "getTime", "getFullYear", "getMonth", "has", "includes", "indexOf", "isArray",
    "isFinite", "isInteger", "join", "json", "keys", "map", "match", "max", "min", "open",
    "prepend", "preventDefault", "push", "querySelector", "querySelectorAll", "reduce", "reload",
    "replace", "replaceState", "reset", "reverse", "round", "scrollIntoView", "setAttribute",
    "setDate", "setItem", "shift", "showModal", "slice", "some", "sort", "splice", "split",
    "startsWith", "stringify", "substr", "substring", "then", "text", "toBlob", "toFixed",
    "toLowerCase", "toISOString", "toJSON", "toUpperCase", "trim", "trimStart", "unshift", "values",
    "writeText", "observe", "disconnect", "unobserve", "scrollTo", "scrollBy", "append",
    "removeChild", "remove", "insertBefore", "matches", "blur", "select", "submit", "reportValidity",
    "toggle", "focusin", "focusout", "pop", "flat", "flatMap", "padStart", "padEnd", "repeat",
}

RESERVED = {
    "async", "await", "var", "let", "const", "function", "if", "else", "for", "while", "switch",
    "case", "break", "continue", "return", "typeof", "instanceof", "new", "class", "try", "catch",
    "finally", "throw", "default", "delete", "in", "of", "yield", "do", "void", "this",
}

BUILTINS = {
    "String", "Number", "Boolean", "Array", "Object", "JSON", "Math", "Date", "Promise", "Set",
    "Map", "RegExp", "Error", "Intl", "FormData", "FileReader", "Blob", "URL", "TextEncoder",
    "structuredClone", "queueMicrotask", "requestAnimationFrame", "setTimeout", "clearTimeout",
    "setInterval", "clearInterval", "fetch", "encodeURIComponent", "decodeURIComponent", "alert",
    "confirm", "prompt", "isNaN", "parseInt", "parseFloat", "NaN", "Infinity", "undefined",
    "navigator", "document", "window", "localStorage", "sessionStorage", "history", "location",
    "console", "HTMLDetailsElement", "Event", "CustomEvent", "DOMParser", "AbortController",
}


def test_app_js_defines_all_handlers() -> None:
    """Jeder im HTML/JS verdrahtete Handler muss als Funktion existieren."""
    source = APP_JS.read_text(encoding="utf-8")
    required = [
        "submitDebate",
        "forkDebate",
        "deleteDebate",
        "renderTranscript",
        "renderTurn",
        "renderModeration",
        "renderJudgment",
        "loadDebateCalls",
        "renderCall",
        "renderProviders",
        "renderProviderConfig",
        "selectProvider",
        "testProvider",
        "saveProvider",
        "loadProviders",
        "currentProviderId",
        "providerById",
        "providerLabel",
        "groupLabel",
        "loadConfig",
        "loadSystem",
        "renderSystem",
        "renderModeBadges",
        "activateTab",
        "bindStaticEvents",
        "setDefaultDates",
        "copyText",
        "statusChip",
        "statusLabel",
    ]
    missing = [name for name in required if not re.search(rf"function\s+{name}\s*\(", source)]
    assert missing == [], f"Funktionen fehlen in app.js: {missing}"


def test_html_has_all_controls() -> None:
    html = (APP_JS.parent.parent / "templates" / "index.html").read_text(encoding="utf-8")
    required = [
        'id="debate-rounds"',
        'id="debate-detail"',
        'id="debate-list"',
        'id="debate-more"',
        'id="provider-grid"',
        'id="provider-config-card"',
        'id="provider-test"',
        'id="provider-save"',
        'id="fork-dialog"',
        'id="fork-topic"',
        'id="fork-rounds"',
        'id="cfg-confidence"',
        'id="cfg-show-reasoning"',
        'id="cfg-early-stop"',
        'data-panel="providers"',
    ]
    missing = [needle for needle in required if needle not in html]
    assert missing == [], f"Bedienelemente fehlen im Template: {missing}"


def test_provider_scripts_are_wired() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    for selector in (
        "#provider-grid",
        "#provider-test",
        "#provider-save",
        "#provider-base-url",
        "#provider-api-key",
        "#provider-model",
        "#fork-form",
        "#fork-submit",
        "#fork-cancel",
    ):
        assert selector in source, f"Selector {selector} wird nicht verdrahtet"


def test_rounds_input_is_numeric_and_unbounded() -> None:
    html = (APP_JS.parent.parent / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="debate-rounds" name="rounds" type="number" min="1" max="2000"' in html
    assert 'id="fork-rounds"' in html
    source = APP_JS.read_text(encoding="utf-8")
    assert "rounds > 2000" in source or "rounds > 2000" in source.replace("  ", " ")
    assert '<option value="8" selected>' not in html, "Runden-Dropdown begrenzt weiterhin auf 8"


def test_app_js_has_no_undefined_calls() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    defined = set(re.findall(r"function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", source))
    defined |= set(
        re.findall(r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(", source)
    )
    defined |= set(
        re.findall(r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?function", source)
    )
    called = set(re.findall(r"\b([a-z_$][A-Za-z0-9_$]*)\s*\(", source))
    unknown = sorted(
        name
        for name in called - defined - METHODS - RESERVED - BUILTINS
        if not name.startswith("_")
    )
    assert defined
    assert unknown == [], f"nicht definierte Funktionsaufrufe: {unknown}"