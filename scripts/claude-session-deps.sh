#!/bin/bash
# Bereitet eine Cloud-Session vor: Datenbankdienst starten, .venv mit den
# Projekt-Abhängigkeiten anlegen. Lokal passiert nichts — dort gibt es beides
# bereits. Als SessionStart-Hook zu registrieren, siehe docs/claude-cloud-setup.md.

set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

# PostgreSQL: das gespeicherte Abbild der Umgebung hält Dateien, keine
# Prozesse. Die Datenbank sportfabrik_dev ist also da, der Dienst läuft aber
# nicht — DATABASE_URL zeigt auf localhost:5432.
if command -v pg_isready >/dev/null 2>&1; then
  pg_isready --quiet || service postgresql start >/dev/null 2>&1 || true
  for _ in $(seq 1 10); do
    pg_isready --quiet && break
    sleep 1
  done
fi

# .venv statt Systempython: dort scheitert "pip install -r requirements.txt"
# am Debian-Paket PyYAML, das pip nicht ersetzen darf. pyrightconfig.json
# erwartet ohnehin ein .venv im Projekt.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

# pytest steht bewusst nicht in requirements.txt (nur Laufzeit), wird aber für
# die Testsuite gebraucht — siehe README, Abschnitt "Tests".
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt pytest

# Damit pytest, python und alembic in der Session ohne Pfadangabe das .venv
# treffen.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
