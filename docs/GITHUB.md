# GitHub

## Repository

**https://github.com/Elpablo777/menschheit-arena** – öffentlich, Default-Branch `main`, 3 Commits.

```bash
git clone https://github.com/Elpablo777/menschheit-arena.git
cd menschheit-arena
./start.sh            # oder . .\start.ps1
```

CI läuft bei jedem Push: Tests auf Python 3.11–3.13, Ruff und `menschheit doctor`.

## Nach dem Klonen

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
menschheit setup          # Provider, Modelle, Key
menschheit doctor
menschheit serve
```

Der Demo-Modus braucht weder Key noch Netzwerk.

## „Alte Beschreibungen" bearbeiten

## Vor dem ersten Commit prüfen

- `.env` ist nicht enthalten (`.gitignore` deckt `.env` und `.env.*` mit Ausnahme von `.env.example`).
- `data/`, `reports/`, `__pycache__`, `.venv`, `.pytest_cache` sind ignoriert.
- Keine echten API-Keys im Code. Der Provider-Katalog enthält nur Modellnamen, keine Keys.
- `.env.bak-*` Backups aus `/api/providers/select` tauchen wegen `.env.*` nicht im Repo auf.

## „Alte Beschreibungen" bearbeiten

Im Arbeitsverzeichnis `C:\Users\Pablo\Documents\Standardprojekt` existieren keine weiteren Projektdateien oder Repos zu diesem Thema. Es gibt also keine alten READMEs oder Beschreibungen, die hätten aktualisiert werden können – das Projekt ist eine Neuanlage. Falls später Repos dazukommen, die auf die Arena verweisen, gehören folgende Stellen aktualisiert:

- README-Beschreibung und Top-Level-README
- `docs/ARCHITEKTUR.md`, `docs/BETRIEB.md`
- `.env.example`, falls sich Variablennamen ändern
- `pyproject.toml` (Version, Beschreibung)

## CI

`.github/workflows/ci.yml` läuft bei Push und PR: Tests, Ruff, `menschheit doctor`. Der Workflow braucht kein Secret, weil die Tests im Mock-Modus ohne Netz laufen.

## Release

Tag setzen, `python -m build`, `twine upload` – oder einfach als GitHub-Release mit dem generierten Wheel. Versionen werden in `pyproject.toml` und `src/menschheit/config.py` (`Settings.version`) gepflegt; beide müssen zusammenpassen.