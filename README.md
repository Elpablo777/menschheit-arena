# Menschheit Arena

**Zwei Säulen, ein lokaler Start:** eine Multi-Agenten-Debatten-Arena (Pro Menschheit gegen Contra Menschheit) und Sentinel Lab, eine Pentest-Control-Plane mit Scope-Enforcement und Human-in-the-Loop.

Die App läuft ohne API-Key im deterministischen Demo-Modus. Erst wenn Modellnamen und ein Key hinterlegt sind, gehen echte LLM-Anfragen raus. Standard ist OpenRouter mit `:free`-Modellen, damit die App ohne Guthaben startet.

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│ Arena                       │     │ Sentinel Lab                 │
│ Pro  ⇄  Contra  (Steel­man)  │     │ Scope-Guard → Plan → Approval│
│ Moderator (Anti-Sycophancy) │     │ Kill-Switch → Audit-Kette    │
│ Richter (Dual-Order)        │     │ Findings nur nach Human-Review│
└─────────────────────────────┘     └──────────────────────────────┘
```

## Schnellstart

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/mac: source .venv/bin/activate
pip install -e ".[dev]"

menschheit demo      # eine vollständige Demo-Debatte ohne API-Key
menschheit serve     # http://127.0.0.1:8000
```

`menschheit setup` führt interaktiv durch Provider, Modellnamen und Key und schreibt eine `.env` (bestehende Datei wird vorher gesichert). `menschheit doctor` prüft Konfiguration, Prompt-Ressourcen, Datenbank und Audit-Kette.

### Startskripte

- Windows: `.\start.ps1` (Setup-Venv, `pip install -e .`, `menschheit doctor`, `menschheit serve`)
- Linux/macOS: `./start.sh` (identisch)
- Container: `docker compose up --build` → http://127.0.0.1:8000

## Provider

`menschheit providers` zeigt alle Presets. Der LLM-Layer spricht ausschließlich OpenAI-kompatible `/chat/completions`-Endpunkte.

| Provider      | Beispiel-Modelle                                | Hinweis                        |
| ------------- | ----------------------------------------------- | ------------------------------ |
| `mock`        | `mock-*`                                        | deterministisch, offline       |
| `openrouter`  | `anthropic/claude-...`, `deepseek/deepseek-r1`  | viele Modelle, ein Key         |
| `deepseek`    | `deepseek-chat`, `deepseek-reasoner`            | günstig, gute Reasoning-Modelle|
| `openai`      | `gpt-4.1`, `gpt-4.1-mini`                       |                                |
| `mistral`     | `mistral-large-latest`                          | EU-Endpunkt, AVV prüfen        |
| `ollama`      | `llama3.1`, `qwen2.5`                           | lokal, kein Cloud-Transfer     |
| `litellm`     | `arena-pro-model`                               | eigener Proxy                  |
| `openai_compat`| beliebig                                       | `LLM_BASE_URL` frei wählbar    |

Jede Rolle kann ein eigenes Modell bekommen (`ARENA_PRO_MODEL`, `ARENA_CONTRA_MODEL`, `ARENA_JUDGE_MODEL`, `ARENA_MODERATOR_MODEL`) oder im UI-Formular pro Debatte überschrieben werden. Energie- und Kostenargumente: Der Bericht weist Token-Zahlen aus; `cost_usd` bleibt 0, weil keine Preisdaten hinterlegt sind.

## Was die Arena anders macht

- **Isolation:** Pro und Contra sehen vor ihrer ersten Runde nur das Thema und ihr eigenes Prompt-Paket – nicht die Position des anderen.
- **Steel­man-Pflicht:** Jede Antwort beginnt mit der stärksten Gegenposition. Danach folgt das öffentliche Argument.
- **Internes Reasoning:** Der private Gedankengang wird gespeichert, aber nie an den Gegner übergeben (siehe `web/templates/index.html`, aufklappbar nur in der Detailansicht).
- **Anti-Sycophancy:** Der Moderator bewertet jede Runde. Zustimmung („CONVINCED") zählt nur, wenn mindestens eine Seite ihr Konfidenz-Gate von 25 erreicht hat – das prüft der Code, nicht das Modell.
- **Dual-Order-Richter:** Gepasst wird in A/B und B/A. Die Differenz der Punktesummen ist das ausgewiesene Positionsbias-Delta.
- **Toulmin-Prüfung:** Der Richter trennt *surviving claims*, *refuted claims* und *open conflicts* und leitet daraus konkrete Architektur- bzw. Verfassungsregeln ab.
- **Stop-Gründe:** `CONVINCED`, `SYNTHESIS_REACHED`, `DEADLOCK` – nie ein „wir sind uns einig" ohne Beleg.
- **Bericht:** Markdown mit Executive Summary, Punktwertung, dokumentierten Grundsatzkonflikten und vollständigem öffentlichem Transkript.

### HTTP-API

| Methode | Pfad | Zweck |
| --- | --- | --- |
| GET | `/api/health` | Status, DB, Provider |
| GET | `/api/config` | öffentliche Konfiguration (ohne Key) |
| GET | `/api/providers` | Anbieter-Katalog mit `:free`-Markierung |
| POST | `/api/providers/test` | Verbindung testen, ohne etwas zu ändern |
| POST | `/api/providers/select` | Provider dauerhaft in `.env` speichern |
| GET | `/api/i18n/{de|en}` | UI-Texte |
| POST | `/api/arena/debates` | Debatte starten (`sync: true` für synchron) |
| GET | `/api/arena/debates` | Liste mit Rundenzahlen |
| GET | `/api/arena/debates/{id}` | Detail inkl. Turns, Moderationen, Urteil |
| GET | `/api/arena/debates/{id}/transcript` | vollständiger Verlauf je Runde |
| GET | `/api/arena/debates/{id}/calls` | LLM-Aufrufe mit Prompt, Antwort, Tokens |
| POST | `/api/arena/debates/{id}/fork` | neue Debatte aus dieser, mit neuem Thema |
| DELETE | `/api/arena/debates/{id}` | Debatte und Protokoll löschen |
| GET | `/api/arena/debates/{id}/report.md` | Markdown-Bericht |
| GET | `/api/prompts/{role}/{lang}` | System-Prompt einer Rolle als Rohtext |
| POST | `/api/sentinel/engagements` | Engagement anlegen (RoE, Scope, Ports) |
| GET | `/api/sentinel/engagements` | Liste |
| GET | `/api/sentinel/engagements/{id}` | Detail inkl. Aktionen, Findings, Audit |
| POST | `/api/sentinel/engagements/{id}/plan` | Aktionsplan (`rules` oder `llm`) |
| POST | `/api/sentinel/actions/{id}/approve` | dokumentierte Freigabe |
| POST | `/api/sentinel/actions/{id}/reject` | Ablehnung mit Grund |
| POST | `/api/sentinel/engagements/{id}/kill` | Kill-Switch |
| POST | `/api/sentinel/engagements/{id}/findings` | menschlich verifiziertes Finding |
| DELETE | `/api/sentinel/engagements/{id}` | Engagement löschen |
| GET | `/api/sentinel/engagements/{id}/report.md` | Markdown-Bericht |
| POST | `/api/sentinel/validate` | Scope-Check ohne Nebenwirkung |
| GET | `/api/audit` | Status der Audit-Kette |

### Protokoll lesen

Ein Klick auf eine Debatte öffnet den vollständigen Verlauf: Thema, jede Runde mit beiden Beiträgen, Steelman, öffentlichem Argument, Konfidenz, Zugeständnissen und Falsifikationsbedingung. Eine separate Moderationskarte zeigt Zusammenfassung, erkannte Muster und die Direktive für die nächste Runde. „Verwendete Prompts" springt zu den LLM-Aufrufen und zeigt den System-Prompt, die Benutzer-Nachricht und die Antwort im Klartext – inklusive Token-Zahlen und Dauer.

„Als neue Debatte starten" öffnet einen Dialog, übernimmt Modelle und Einstellungen und startet mit einem anderen Thema. Die alte Debatte bleibt unverändert erhalten.

Fehlerhafte Debatten (Status `failed`) bleiben sichtbar; der Fehlertext wird unter „Fehlerdetails" angezeigt, statt die Liste leer zu lassen.

Schreibende Zugriffe sind über `APP_ACCESS_TOKEN` schützbar (Header `X-App-Token` oder `Authorization: Bearer`). Ohne Token nicht auf `0.0.0.0` binden.

## Sentinel Lab: Grenzen sind der Zweck

In v0.1 ist Sentinel eine **Control Plane**, kein Scanner:

- Scope-Guard mit CIDR, Domain, URL, Port-Allowlist. Öffentliche Ziele sind per Default gesperrt (`ALLOW_PUBLIC_TARGETS=false`), Wildcards wie `*` oder `0.0.0.0/0` werden abgelehnt, URL-Credentials ebenfalls.
- Aktionen werden **vorgeschlagen** und in `READ_ONLY` / `ACTIVE_REQUIRES_APPROVAL` eingeteilt. Ausführung passiert hier nicht – `PENTEST_EXECUTION_ENABLED=false` ist gesetzt und in v0.1 nicht implementiert.
- Freigaben sind namentlich, mit Zeitstempel, im Audit-Log. Ohne Freigabe bleibt eine aktive Aktion `proposed`.
- Findings erscheinen nur nach Häkchen „menschlich verifiziert" im Bericht.
- Der RoE-Text wird als SHA-256 im Engagement gespeichert; die Audit-Kette ist append-only (SQLite-Trigger + Hash-Verkettung über `seq`).
- Kill-Switch setzt alle offenen/ freigegebenen Aktionen auf `rejected` und sperrt weitere Planung.

Damit ist die Kette bewusst unvollständig: Planung, Freigabe, Nachweis, Bericht. Wer tatsächlich scannen will, koppelt eigene Executor an die freigegebenen Aktionen – außerhalb dieses Repos und nur im erlaubten Scope.

## Konfiguration

Alle Werte stehen in `.env.example`. Der LLM-Layer spricht ausschließlich OpenAI-kompatible `/chat/completions`-Endpunkte. Über die Seite **Modelle** lässt sich der Anbieter auswählen, die Verbindung testen und als Standard in die `.env` schreiben (bestehende Datei wird vorher gesichert).

| Anbieter | Gruppe | Kostenlos | Hinweis |
| --- | --- | --- | --- |
| `openrouter` | Cloud | 8 `:free`-Modelle | voreingestellt, ein Key für viele Modelle |
| `deepseek` | Cloud | nein | günstig, starke Reasoning-Modelle |
| `openai` | Cloud | nein | zuverlässig |
| `mistral` | Cloud | nein | EU-Endpunkt, AVV prüfen |
| `groq` | Cloud | Freikontingent | sehr schnell |
| `ollama` | Lokal | ja | kein Cloud-Transfer, kein Key |
| `litellm` | Selbst gehostet | ja | eigener Proxy |
| `custom` | Frei | – | beliebige OpenAI-kompatible URL |
| `mock` | Lokal | ja | deterministisch, offline |

Jede Rolle kann ein eigenes Modell bekommen (`ARENA_PRO_MODEL`, `ARENA_CONTRA_MODEL`, `ARENA_JUDGE_MODEL`, `ARENA_MODERATOR_MODEL`) oder pro Debatte im UI überschrieben werden.

Kostenlose OpenRouter-Modelle tragen das Suffix `:free`. Die Auswahl ist voreingestellt, damit die App ohne Guthaben läuft; Rate-Limits sind dort strenger.

## Debatten einstellen

- **Runden:** frei von 1 bis 2000. Der Verlauf zeigt jede Runde einzeln, nicht nur das Endergebnis.
- **Wortlimit pro Beitrag** (80–4000), **Temperatur** (0–2), **maximale Antwort-Tokens** (128–32000).
- **Konfidenz-Gate:** ab welchem Wert „CONVINCED" akzeptiert wird (Standard 25).
- **Früher Stop** an/aus: erlaubt dem Moderator, bei echtem Konsens vor dem Rundenziel zu beenden.
- **Internes Reasoning anzeigen:** blendet den privaten Gedankengang im Protokoll ein oder aus.

`DATABASE_URL` akzeptiert auch Postgres (`postgresql+psycopg://...`), dann `pip install -e ".[postgres]"`. Relative SQLite-Pfade werden relativ zur Projektwurzel aufgelöst.

## Sprache

Standard ist Deutsch (`APP_LANG=de`), vollständig umschaltbar auf Englisch – UI, Prompts, Wissen, Berichte. Der Sprachumschalter oben rechts schreibt die Wahl in den `localStorage`. Fehlt ein Schlüssel, wird der Rohschlüssel angezeigt, nicht geraten.

## Entwicklung

```bash
pip install -e ".[dev]"
menschheit doctor
pytest -q
ruff check src tests
menschheit serve --reload
```

Tests decken i18n-Vollständigkeit, JSON-Parsing (Zäune, Aliase, abgeschnittene Objekte), Konfidenz-Parsing, Richter-Score-Neuberechnung, Scope-Guard (CIDR, Wildcard, öffentliche Ziele, Ports), den kompletten API-Fluss inkl. Token-Middleware sowie Audit-Kette und Append-only-Trigger ab.

## Projektstruktur

```
src/menschheit/
  api/          FastAPI-Routen, Schemas, Token-Middleware
  debate/       Engine, Prompt-Parser, Modelle, Report-Generator
  i18n/         de.json / en.json, identische Schlüssel
  knowledge/    Argumentations-Dossier je Sprache
  llm/          OpenAI-kompatibler Client, Mock-Client, Provider-Auswahl
  prompts/      pro/contra/moderator/judge/planner je Sprache
  sentinel/     Scope-Guard, Regel-Planer, Service, Reports
  storage/      SQLite/Postgres, Repository, Audit-Kette
  web/          Vanilla-JS-SPA ohne Build-Schritt
tests/          53 Tests
```

Keine externen Assets, kein CDN, kein Build. `web/` wird von Jinja ausgeliefert, `app.js` rendert die Ansichten mit `textContent` bzw. `escapeHtml` an allen dynamischen Stellen.

## Sicherheit und Recht

- Keine aktive Ausführung, keine Payloads, keine Exfiltration im Repo.
- Der Host, auf dem die App läuft, führt keine Scans gegen Dritte aus. Sentinel plant und protokolliert nur.
- Vor einem echten Pentest: schriftliche RoE, benannter Freigebender, Notfallkontakt, Scope-Liste, Zeitfenster, Datenhaltung, Löschkonzept, AVV mit dem Model-Anbieter, Prüfung nach EU AI Act (Transparenzpflichten).
- Audit-Logs und Debattenarchive können personenbezogene Daten enthalten. Die Vorlagen in `legal/` sind Startpunkte, keine Rechtsberatung.
- Modelle können falsche oder manipulierte Ausgaben erzeugen. Der Richter ist ein zweiter Aufruf, keine Wahrheitsinstanz.

Details: `docs/ARCHITEKTUR.md`, `docs/SICHERHEIT.md`, `docs/BETRIEB.md`, `docs/HERMES.md`, `docs/GITHUB.md`, `legal/`.

## Lizenz

MIT. Modelle und Endpunkte unterliegen den Bedingungen ihrer Anbieter.