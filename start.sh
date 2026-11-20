#!/usr/bin/env bash
# Menschheit Arena - Startskript (Linux/macOS).
# Legt .venv an, installiert das Paket, prueft die Konfiguration und startet den Server.
set -euo pipefail

cd "$(dirname "$0")"

VENV_PYTHON=".venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Erstelle virtuelle Umgebung (.venv) ..."
    python3 -m venv .venv
fi

echo "Installiere Paket ..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -e ".[dev]"

echo "Pruefe Konfiguration ..."
if ! "$VENV_PYTHON" -m menschheit.cli doctor; then
    echo "doctor meldet Fehler. Behebe sie, bevor du startest." >&2
    exit 1
fi

echo
echo "Starte Menschheit Arena ..."
echo "Danach: http://127.0.0.1:8000"
echo

exec "$VENV_PYTHON" -m menschheit.cli serve "$@"