# Betrieb

## Voraussetzungen

- Python 3.11+
- SQLite (Standard) oder Postgres 14+
- Für Live-Betrieb: OpenAI-kompatibler Endpunkt + Key

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
menschheit setup                 # schreibt .env, sichert vorhandene Datei
menschheit doctor
menschheit serve
```

## Startskripte

`start.ps1` / `start.sh` legen das Venv an, installieren das Paket, prüfen mit `doctor` und starten den Server. Beide brechen ab, wenn `doctor` Fehler meldet.

## Container

```bash
docker compose up --build
```

Das Image läuft als nicht-root Benutzer, persistiert `data/` und `reports/` in Volumes und setzt `PENTEST_EXECUTION_ENABLED=false` sowie `ALLOW_PUBLIC_TARGETS=false`.

## Health & Diagnose

- `GET /api/health` – Status, DB, Provider, Mock-Flag
- `menschheit doctor` – `.env`, Provider-URL, Prompt-Ressourcen, UI-Dateien, DB, Audit-Kette
- `GET /api/config` – öffentliche Werte ohne Key

## Backups

SQLite: Datei `data/menschheit.db` im laufenden Betrieb nicht kopieren. Besser:

```bash
sqlite3 data/menschheit.db ".backup 'backup-$(date +%F).db'"
```

Postgres: `pg_dump`. Reports liegen zusätzlich als Markdown in `reports/`.

Wiederherstellung: Datenbank zurückspielen, `menschheit doctor` läuft und meldet Kettenfehler, falls das Backup inkonsistent ist.

## Logs

uvicorn-Log auf stdout. Audit-Events liegen in der Datenbank, nicht im Dateisystem. Debattenfortschritt wird nur im Speicher gehalten (`app.state.progress`) und ist nach Neustart weg – Status und Ergebnis bleiben in der DB.

## Updates

```bash
git pull
pip install -e ".[dev]"
menschheit doctor
```

Schema-Änderungen werden per `CREATE TABLE IF NOT EXISTS` ergänzt. Es gibt keine Migrationen; bei inkompatiblen Änderungen muss die Datenbank neu aufgesetzt werden (Demo-Daten sind ersetzbar, echte RoE-/Audit-Daten vorher sichern).

## Härtung für Serverbetrieb

1. `APP_ACCESS_TOKEN` setzen, sonst nicht exponieren.
2. Reverse-Proxy mit TLS davorschalten, nur `/api` und `/` freigeben.
3. `ALLOW_PUBLIC_TARGETS=false` und `PENTEST_EXECUTION_ENABLED=false` lassen.
4. `APP_ENV=production` setzen (ändert aktuell nur das Label, ist aber ein nützlicher Marker).
5. Datei-Uploads gibt es nicht – trotzdem Webroot nicht schreibbar halten.
6. Bei Postgres: separaten DB-Nutzer mit minimalen Rechten.

## Kostenkontrolle

`LLM_MAX_TOKENS` und `ARENA_WORD_LIMIT` begrenzen die Ausgaben. Eine Debatte mit 4 Runden und vier Rollen erzeugt ca. 40 Anfragen (8 Turns + 4 Moderationen + 2 Richter, jeweils mit Reparaturversuchen). Token-Zahlen stehen im Abschlussbericht und in `debates.total_tokens`. `cost_usd` bleibt 0, weil keine Preisdaten hinterlegt sind.

Wer harte Limits will, setzt vor den Provider einen Proxy mit Budget.