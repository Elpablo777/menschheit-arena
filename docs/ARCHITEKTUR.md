# Architektur

## Überblick

Eine FastAPI-App, ein Thread-Pool für Debatten, eine SQLite-Datei als Standard. Kein Message-Broker, kein Container-Zwang, kein Build-Schritt für das Frontend.

```
Browser (web/, Vanilla JS)
      │  fetch /api/...
      ▼
FastAPI (api/app.py)
  ├─ Token-Middleware (nur schreibende Zugriffe)
  ├─ Arena-Routen      → debate/engine.py
  └─ Sentinel-Routen   → sentinel/service.py
                              │
      ┌───────────────────────┼───────────────────────┐
      ▼                       ▼                       ▼
llm/openai_compat.py   sentinel/scope.py      storage/repository.py
llm/mock.py            sentinel/planner.py    storage/db.py
      │                                          │
      └──────── debate/prompts.py ───────────────┘
                 debate/parser.py
                 debate/report.py
```

## Schichten

**Präsentation.** `web/` ist eine SPA ohne Framework: `index.html` enthält statische Struktur mit `data-i18n`-Attributen, `app.js` rendert Listen und Details aus JSON, `styles.css` hält das Design. Alle dynamischen Werte laufen durch `escapeHtml`. Sprache kommt von `/api/i18n/{lang}`, nicht aus dem Bundle.

**API.** `api/app.py` enthält Routen und Fehlerübersetzung, `api/schemas.py` die Eingabevalidierung (Pydantic, `extra="forbid"`). Die App wird über `create_app(settings, database)` gebaut, damit Tests eine In-Memory-DB injizieren können.

**Debatte.** `debate/engine.py` ist die Zustandsmaschine:

1. Debatte anlegen (`pending`).
2. Pro-Runde: Pro- und Contra-Äußerung erzeugen – beide sehen nur das Thema und die bisherigen *öffentlichen* Argumente der Gegenseite, nie das interne Reasoning.
3. Moderator bewertet die Runde (Sycophancy, Drift, Entscheidung, Direktive).
4. Code-Gate: `CONVINCED` wird verworfen, wenn keine Seite Konfidenz ≤ 25 hat.
5. Bei `CONTINUE_REFINE` und erreichter Rundenzahl → `DEADLOCK`.
6. Richter in A/B, dann B/A; Delta der Summen = Positionsbias.
7. Bericht erzeugen, `completed` (oder `failed`).

`llm/mock.py` liefert für jede Rolle deterministische Antworten. Dadurch ist die komplette Kette inklusive Parsing, Moderation und Dual-Order-Richter offline testbar.

**Sentinel.** `sentinel/scope.py` ist die einzige Stelle, die über Scope entscheidet. `sentinel/planner.py` erzeugt regelbasierte Aktionsvorschläge (DNS, TLS, Header, Standardpfade) – ausführbar sind sie nicht. `sentinel/service.py` kapselt Approval, Reject, Kill-Switch, Findings und Reports und schreibt bei jeder Zustandsänderung einen Audit-Eintrag.

**Persistenz.** `storage/db.py` definiert das Schema und hält Verbindungen (SQLite mit `check_same_thread=False`, optional Postgres). `storage/repository.py` ist die einzige Stelle mit SQL. Boolean-Spalten werden beim Lesen normalisiert, damit JSON-Antworten echte `true`/`false` enthalten.

## Datenmodell

| Tabelle | Zweck |
| --- | --- |
| `debates` | Thema, Sprache, Modelle, Status, Stop-Grund, Token |
| `turns` | öffentliches Argument, Steelman, internes Reasoning, Konfidenz, Zugeständnisse |
| `moderations` | Zusammenfassung, Sycophancy/Drift, Entscheidung, Direktive |
| `judgments` | A/B- und B/A-Pass, Bias-Delta, Toulmin-Ergebnis, Markdown |
| `engagements` | RoE-Text + SHA-256, Scope, Ports, Freigebender, Laufzeit, Kill-Switch |
| `actions` | Phase, Ziel, Port, Typ, Befehl, Risiko, Scope-Entscheid, Freigabe |
| `findings` | Titel, OWASP, CVSS-Vektor, Evidenz, Remediation, Human-Verifikation |
| `audit_events` | `seq`, `prev_hash`, `hash` – append-only verkettet |

## Audit-Kette

Jeder Eintrag wird aus `prev_hash | created_at | engagement_id | actor | event_type | payload_json` gebildet und als SHA-256 gespeichert. `seq` ist global monoton. In SQLite verhindern Trigger UPDATE und DELETE. `verify_audit_chain()` prüft beide Richtungen: Prev-Hash-Verkettung und neu berechnete Hashes.

Die Kette ist manipulationssicher, aber nicht geheim. Sie schützt gegen nachträgliche Änderungen im aktiven Betrieb, nicht gegen jemanden mit Vollzugriff auf die Datenbank.

## Erweiterungspunkte

- **Neue Provider:** Eintrag in `PROVIDER_PRESETS` genügt, solange der Endpunkt OpenAI-kompatibel ist.
- **Neue Rollen:** `llm/build_client` und `_normalise_turn` ergänzen; Prompt-Datei anlegen.
- **Eigene Executor:** An `service.approve_action` andocken, freigegebene Aktionen abgreifen. Nicht in diesem Repo.
- **Hermes:** Kein nativer Raum. Anbindung über REST, siehe `HERMES.md`.

## Grenzen

Keine Persistenz-Migrationen (Schema wird per `CREATE TABLE IF NOT EXISTS` angelegt), keine Multi-Tenant-Trennung über `tenant_id` hinaus, keine Rate-Limits, keine WebSocket-Streams (Polling alle 1,4 s), kein Nutzerkonto.