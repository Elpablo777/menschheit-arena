# GitHub

## Status

Das Projekt ist lokal unter `menschheit-arena/` vollständig angelegt und als Git-Repo mit einem Commit auf `main` vorbereitet. Auf GitHub liegt es noch nicht, weil `gh` nicht angemeldet ist:

```
You are not logged into any GitHub hosts.
```

Letzter Schritt danach:

```bash
gh auth login
gh repo create menschheit-arena --public --source=. --push
```

## Vor dem ersten Commit prüfen

- `.env` ist nicht enthalten (`.gitignore` deckt `.env` und `.env.*` mit Ausnahme von `.env.example`).
- `data/`, `reports/`, `__pycache__`, `.venv`, `.pytest_cache` sind ignoriert.
- Keine echten API-Keys im Code. `menschheit doctor` zeigt maskierte Werte, keine Klartext-Keys.

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