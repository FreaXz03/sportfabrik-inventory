#!/bin/bash
# Richtet in Cloud-Sessions ein .venv mit den Projekt-Abhängigkeiten ein, damit
# dort pytest und die App laufen. Lokal passiert nichts — dort gibt es das .venv
# bereits. Als SessionStart-Hook zu registrieren, siehe docs/claude-cloud-setup.md.
#
# Warum ein .venv und nicht der Systempython: der Container bringt die
# Abhängigkeiten nicht mit, und die Debian-Pakete des Systempythons kollidieren
# mit den Pins in requirements.txt (pip kann PyYAML nicht ersetzen).
# pyrightconfig.json zeigt ohnehin auf .venv.

set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

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
