"""Kommandozeile: Setup, Server, Demo-Debatte und Diagnose."""

from __future__ import annotations

import argparse
import getpass
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from . import __version__
from .config import PROJECT_ROOT, Settings, get_settings, reload_settings
from .debate.engine import DebateEngine
from .i18n import normalize_lang, t, validate_catalogs
from .llm import build_client
from .llm.base import LLMError
from .llm.mock import MockLLM
from .providers import PROVIDER_ORDER, PROVIDERS, catalogue
from .storage import Database, Repository

ENV_PATH = PROJECT_ROOT / ".env"
REPORT_DIR = PROJECT_ROOT / "reports"


# ---------------------------------------------------------------- Hilfsmittel


def _line(key: str, value: str) -> str:
    value = str(value).replace("\n", " ").replace("\r", " ").strip()
    if " " in value or "#" in value or '"' in value:
        value = '"' + value.replace('"', "'") + '"'
    return f"{key}={value}"


def _mask(value: str) -> str:
    if not value:
        return "(leer)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-3:]}"


def _safe_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        return value
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or default


def _ask_bool(prompt: str, default: bool = False) -> bool:
    marker = "J/n" if default else "j/N"
    raw = input(f"{prompt} ({marker}): ").strip().lower()
    if not raw:
        return default
    return raw in {"j", "ja", "y", "yes", "1", "true"}


def _choose_provider(default: str = "mock") -> str:
    names = [name for name in PROVIDERS if name in PROVIDER_ORDER] + [
        name for name in PROVIDERS if name not in PROVIDER_ORDER
    ]
    print("\nProvider:")
    for index, name in enumerate(names, start=1):
        info = PROVIDERS[name]
        label = info.get("label_de") or info["label"]
        note = ""
        if name == "mock":
            note = "  (ohne API-Key, deterministisch)"
        elif name == "openrouter":
            note = f"  ({len(info['models'])} Modelle, davon {sum(1 for m in info['models'] if str(m['id']).endswith(':free'))} kostenlos)"
        print(f"  {index:2d}. {name:12s} {label}{note}")
    raw = _ask("Auswahl (Name oder Nummer)", default)
    if raw.isdigit() and 1 <= int(raw) <= len(names):
        return names[int(raw) - 1]
    return raw if raw in names else default


def _write_env(values: dict[str, str]) -> Path:
    if ENV_PATH.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = ENV_PATH.with_name(f".env.bak-{stamp}")
        shutil.copy2(ENV_PATH, backup)
        print(f"  Sicherung: {backup.name}")
    lines = [
        "# Erzeugt von `menschheit setup`.",
        "# Diese Datei enthaelt Secrets. Nicht committen.",
        "",
    ]
    for key, value in values.items():
        lines.append(_line(key, value))
    ENV_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return ENV_PATH


def _save_report(debate: dict) -> Path:
    judgment = debate.get("judgment") or {}
    markdown = judgment.get("final_report_md") or ""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"debate-{debate['id']}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def _print_result(debate: dict, report_path: Path) -> None:
    judgment = debate.get("judgment") or {}
    toulmin = judgment.get("toulmin") or {}
    winner = toulmin.get("winner") or (judgment.get("pass_ab") or {}).get("winner") or "draw"
    lang = normalize_lang(debate.get("language", "de"))
    label = {
        "pro": t("arena.turn.pro", lang),
        "contra": t("arena.turn.contra", lang),
        "draw": t("report.draw", lang),
    }.get(winner, winner)
    print()
    print(f"Status:      {debate.get('status')}")
    print(f"Abbruch:     {debate.get('stop_reason') or '-'}")
    print(f"Urteil:      {label}")
    print(f"Tokens:      {debate.get('total_tokens', 0)}")
    print(f"Bericht:     {report_path}")
    if debate.get("error"):
        print(f"Fehler:      {debate['error']}")


def _create_debate(settings: Settings, repo: Repository, topic: str, rounds: int, lang: str) -> dict:
    models = {
        "pro": settings.pro_model,
        "contra": settings.contra_model,
        "judge": settings.judge_model,
        "moderator": settings.moderator_model,
    }
    return repo.create_debate(
        topic=topic,
        language=normalize_lang(lang),
        rounds_requested=max(1, min(rounds, settings.max_rounds)),
        models=models,
    )


def _run(
    settings: Settings,
    repo: Repository,
    client,
    topic: str,
    rounds: int,
    lang: str,
    quiet: bool = False,
) -> dict:
    debate = _create_debate(settings, repo, topic, rounds, lang)
    progress = None if quiet else (lambda message: print(f"  · {message}"))
    engine = DebateEngine(settings, repo, client, progress=progress)
    result = engine.run(debate["id"])
    report_path = _save_report(result)
    _print_result(result, report_path)
    return result


# ---------------------------------------------------------------- Kommandos


def cmd_setup(args: argparse.Namespace) -> int:
    print(f"Menschheit Arena {__version__} – Setup")
    print("Der Demo-Modus funktioniert ohne API-Key. Live-Modelle brauchen einen Key.\n")

    interactive = not args.yes
    provider = args.provider or (_choose_provider("mock") if interactive else "mock")
    if provider not in PROVIDERS:
        print(f"Unbekannter Provider: {provider}")
        return 2
    preset = {
        "base_url": "",
        "pro": "",
        "contra": "",
        "judge": "",
        "moderator": "",
    }
    info = PROVIDERS[provider]
    preset["base_url"] = info.get("base_url", "")
    preset.update(info.get("defaults", {}))

    base_url = args.base_url or (preset["base_url"] if not interactive else _ask("Base-URL", preset["base_url"]))
    api_key = args.api_key or ""
    if interactive and not api_key and provider not in {"mock", "ollama", "litellm"}:
        api_key = getpass.getpass("API-Key (Eingabe bleibt unsichtbar, leer = später setzen): ").strip()

    pro = args.pro_model or (preset["pro"] if not interactive else _ask("Pro-Modell", preset["pro"]))
    contra = args.contra_model or (
        preset["contra"] if not interactive else _ask("Contra-Modell", preset["contra"])
    )
    judge = args.judge_model or (preset["judge"] if not interactive else _ask("Richter-Modell", preset["judge"]))
    moderator = args.moderator_model or (
        preset["moderator"] if not interactive else _ask("Moderator-Modell", preset["moderator"])
    )
    lang = args.lang or ("de" if not interactive else _ask("Standardsprache (de/en)", "de"))
    try:
        rounds = int(args.rounds or ("4" if not interactive else _ask("Standard-Runden (1-2000)", "4")))
    except ValueError:
        rounds = 4
    rounds = max(1, min(rounds, 2000))
    host = args.host or ("127.0.0.1" if not interactive else _ask("Host", "127.0.0.1"))
    try:
        port = int(args.port or ("8000" if not interactive else _ask("Port", "8000")))
    except ValueError:
        port = 8000
    access_token = args.access_token or ("" if not interactive else _ask("App-Token (leer = offen, nur lokal empfohlen)", ""))

    values = {
        "APP_ENV": "local",
        "APP_LANG": normalize_lang(lang),
        "APP_ACCESS_TOKEN": access_token,
        "HOST": host,
        "PORT": str(port),
        "DATABASE_URL": "sqlite:///./data/menschheit.db",
        "LLM_PROVIDER": provider,
        "LLM_BASE_URL": base_url,
        "LLM_API_KEY": api_key,
        "LLM_TEMPERATURE": "0.7",
        "LLM_MAX_TOKENS": "1400",
        "LLM_TIMEOUT_SECONDS": "90",
        "ARENA_PRO_MODEL": pro,
        "ARENA_CONTRA_MODEL": contra,
        "ARENA_JUDGE_MODEL": judge,
        "ARENA_MODERATOR_MODEL": moderator,
        "ARENA_DEFAULT_ROUNDS": str(max(1, min(rounds, 2000))),
        "ARENA_MAX_ROUNDS": "2000",
        "ARENA_WORD_LIMIT": "350",
        "PENTEST_EXECUTION_ENABLED": "false",
        "ALLOW_PUBLIC_TARGETS": "false",
    }

    print("\nZusammenfassung:")
    print(f"  Provider:  {provider} – {preset['label']}")
    print(f"  Base-URL:  {base_url or '(leer)'}")
    print(f"  API-Key:   {_mask(api_key)}")
    print(f"  Modelle:   {pro} / {contra} / {judge} / {moderator}")
    print(f"  Server:    http://{host}:{port}")
    print(f"  Sprache:   {normalize_lang(lang)}")
    print("  Grenzen:   PENTEST_EXECUTION_ENABLED=false, ALLOW_PUBLIC_TARGETS=false")

    if ENV_PATH.exists() and not args.yes:
        if not _ask_bool(f"{ENV_PATH.name} existiert. Überschreiben?", False):
            print("Abgebrochen. Bestehende Konfiguration bleibt unverändert.")
            return 1
    path = _write_env(values)
    print(f"\nGespeichert: {path}")
    print("Nächster Schritt:  menschheit demo   oder   menschheit serve")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    settings = get_settings()
    import uvicorn

    host = args.host or settings.host
    port = args.port or settings.port
    print(f"Menschheit Arena {settings.version}")
    print(f"Modus:    {'Demo / Mock' if settings.is_mock else settings.provider}")
    print(f"Adresse:  http://{host}:{port}")
    print(f"Datenbank: {_safe_url(settings.database_url)}")
    if settings.is_mock:
        print("Hinweis:  Demo-Modus ohne externe Modellaufrufe.")
    uvicorn.run(
        "menschheit.api.app:app",
        host=host,
        port=port,
        reload=bool(args.reload),
        log_level=args.log_level,
    )
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    settings = get_settings()
    lang = normalize_lang(args.lang or settings.lang)
    topic = args.topic or t("arena.form.demo_topic", lang)
    db = Database(settings.database_url)
    repo = Repository(db)
    print(f"Demo-Debatte ({lang}), {args.rounds or settings.default_rounds} Runden")
    print(f"Thema: {topic}")
    try:
        _run(settings, repo, MockLLM(), topic, args.rounds or settings.default_rounds, lang)
    except Exception as exc:
        print(f"Fehler: {type(exc).__name__}: {str(exc)[:300]}")
        return 2
    return 0


def cmd_debate(args: argparse.Namespace) -> int:
    settings = get_settings()
    lang = normalize_lang(args.lang or settings.lang)
    topic = " ".join(args.topic).strip()
    if len(topic) < 8:
        print("Thema zu kurz (mindestens 8 Zeichen).")
        return 2
    rounds = args.rounds or settings.default_rounds
    db = Database(settings.database_url)
    repo = Repository(db)
    try:
        client = build_client(settings)
    except LLMError as exc:
        print(f"Provider-Konfiguration fehlerhaft: {exc}")
        return 2
    print(f"Debatte ({lang}), {rounds} Runden, Provider: {settings.provider}")
    print(f"Thema: {topic}")
    try:
        _run(settings, repo, client, topic, rounds, lang)
    except LLMError as exc:
        print(f"LLM-Fehler: {exc}")
        return 2
    except Exception as exc:
        print(f"Fehler: {type(exc).__name__}: {str(exc)[:300]}")
        return 2
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    settings = get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    print(f"Menschheit Arena {__version__} – Doctor")
    print(f"Projekt:   {PROJECT_ROOT}")
    print(f"Python:    {sys.version.split()[0]}")
    print(f"Provider:  {settings.provider} ({settings.public_dict()['provider_label']})")
    print(f"Base-URL:  {_safe_url(settings.llm_base_url) or '(leer)'}")
    print(f"Modelle:   {settings.pro_model} / {settings.contra_model} / {settings.judge_model} / {settings.moderator_model}")
    print(f"Datenbank: {_safe_url(settings.database_url)}")
    print(f"Sprache:   {normalize_lang(settings.lang)}\n")

    if not ENV_PATH.exists():
        warnings.append(".env fehlt; es gelten Standardwerte (Demo-Modus). `menschheit setup` hilft.")
    if not settings.is_mock:
        if not settings.llm_base_url.startswith(("http://", "https://")):
            errors.append("LLM_BASE_URL ist leer oder keine gültige http(s)-URL.")
        if not settings.llm_api_key and settings.provider not in {"ollama", "litellm"}:
            warnings.append("Kein LLM_API_KEY gesetzt; Live-Aufrufe werden voraussichtlich scheitern.")
        if settings.provider == "openai_compat" and "example.invalid" in settings.llm_base_url:
            warnings.append("LLM_BASE_URL zeigt noch auf example.invalid.")

    problems = validate_catalogs()
    if problems:
        errors.extend(problems)

    try:
        from .debate.prompts import load_knowledge, load_prompt

        for lang in ("de", "en"):
            for name in ("pro", "contra", "moderator", "judge", "planner"):
                if not load_prompt(name, lang).strip():
                    errors.append(f"Prompt leer: {lang}/{name}.md")
            if not load_knowledge(lang).strip():
                errors.append(f"Wissensbasis leer: {lang}")
    except Exception as exc:
        errors.append(f"Prompt-Ressourcen nicht lesbar: {type(exc).__name__}: {exc}")

    for relative in ("web/templates/index.html", "web/static/app.js", "web/static/styles.css"):
        if not (Path(__file__).resolve().parent / relative).exists():
            errors.append(f"UI-Datei fehlt: {relative}")

    try:
        db = Database(settings.database_url)
        if not db.health():
            errors.append("Datenbank nicht erreichbar.")
        else:
            repo = Repository(db)
            valid, chain_errors = repo.verify_audit_chain()
            if not valid:
                errors.append("Audit-Kette ungültig: " + "; ".join(chain_errors[:3]))
    except Exception as exc:
        errors.append(f"Datenbankprüfung fehlgeschlagen: {type(exc).__name__}: {exc}")

    if settings.pentest_execution_enabled:
        warnings.append("PENTEST_EXECUTION_ENABLED=true ist gesetzt, aber in v0.1 nicht implementiert.")
    if settings.allow_public_targets:
        warnings.append("ALLOW_PUBLIC_TARGETS=true: Nur mit schriftlicher RoE und Rechtsprüfung zulässig.")
    if not settings.access_token and settings.host not in {"127.0.0.1", "localhost", "::1"}:
        warnings.append("Server bindet auf eine nicht-lokale Adresse ohne APP_ACCESS_TOKEN.")

    print("Prüfungen:")
    print("  [ok]   i18n-Kataloge vollständig" if not problems else "  [fail] i18n-Kataloge unvollständig")
    for warning in warnings:
        print(f"  [warn] {warning}")
    for error in errors:
        print(f"  [fail] {error}")
    if not errors and not warnings:
        print("  Alles in Ordnung.")
    print()
    return 1 if errors else 0


def cmd_providers(_: argparse.Namespace) -> int:
    print("Verfügbare Provider:\n")
    for info in catalogue():
        models = info.get("models") or []
        free = sum(1 for model in models if str(model.get("id", "")).endswith(":free"))
        print(f"{info['id']}  ({info.get('group', 'cloud')})")
        print(f"  {info.get('label_de') or info['label']}")
        print(f"  Base-URL: {info.get('base_url') or '(keine)'}")
        if models:
            shown = ", ".join(model["id"] for model in models[:4])
            suffix = f" (+{len(models) - 4} weitere)" if len(models) > 4 else ""
            print(f"  Modelle:  {shown}{suffix}")
        if free:
            print(f"  Kostenlos: {free} Modelle mit :free")
        if info.get("needs_key"):
            print("  API-Key:  erforderlich")
        elif info["id"] in {"ollama", "mock"}:
            print("  API-Key:  nicht erforderlich")
        print()
    return 0


# ---------------------------------------------------------------- Parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="menschheit",
        description="Menschheit Arena – Multi-Agenten-Debatten und sicheres Pentest-Control-Plane.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Interaktiven Setup-Assistenten starten und .env schreiben.")
    setup.add_argument("--provider", choices=list(PROVIDERS))
    setup.add_argument("--base-url")
    setup.add_argument("--api-key")
    setup.add_argument("--pro-model")
    setup.add_argument("--contra-model")
    setup.add_argument("--judge-model")
    setup.add_argument("--moderator-model")
    setup.add_argument("--lang", choices=["de", "en"])
    setup.add_argument("--rounds", type=int)
    setup.add_argument("--host")
    setup.add_argument("--port", type=int)
    setup.add_argument("--access-token")
    setup.add_argument("--yes", action="store_true", help="Ohne Rückfrage überschreiben.")
    setup.set_defaults(func=cmd_setup)

    serve = sub.add_parser("serve", help="Weboberfläche und API starten.")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument("--log-level", default="info")
    serve.set_defaults(func=cmd_serve)

    demo = sub.add_parser("demo", help="Deterministische Demo-Debatte ohne API-Key ausführen.")
    demo.add_argument("--topic")
    demo.add_argument("--rounds", type=int)
    demo.add_argument("--lang", choices=["de", "en"])
    demo.set_defaults(func=cmd_demo)

    debate = sub.add_parser("debate", help="Debatte mit dem konfigurierten Provider ausführen.")
    debate.add_argument("topic", nargs="+")
    debate.add_argument("--rounds", type=int)
    debate.add_argument("--lang", choices=["de", "en"])
    debate.set_defaults(func=cmd_debate)

    doctor = sub.add_parser("doctor", help="Konfiguration, Ressourcen, Datenbank und Audit-Kette prüfen.")
    doctor.set_defaults(func=cmd_doctor)

    providers = sub.add_parser("providers", help="Provider-Presets anzeigen.")
    providers.set_defaults(func=cmd_providers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "setup" and getattr(args, "yes", False):
        reload_settings()
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 130
    except Exception as exc:
        print(f"Unerwarteter Fehler: {type(exc).__name__}: {str(exc)[:300]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
