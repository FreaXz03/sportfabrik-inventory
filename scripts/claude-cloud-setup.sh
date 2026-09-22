#!/bin/bash
# Setup-Skript für Claude-Code-Cloud-Sessions.
# Einzutragen unter claude.ai/code → Umgebung bearbeiten → Feld "Setup script".
#
# Warum nicht in .claude/settings.json: eine Cloud-Session installiert die dort
# unter "enabledPlugins"/"extraKnownMarketplaces" deklarierten Plugins nicht.
# Nur das Setup-Skript läuft, bevor Claude Code startet — und nur dann sind die
# Plugins in derselben Session geladen. Danach wird das Dateisystem gecacht,
# spätere Sessions starten direkt damit. Details: docs/claude-cloud-setup.md
#
# Das Skript muss mit 0 enden, sonst startet die Session nicht.

set -uo pipefail

MARKETPLACE_REPO="anthropics/claude-plugins-official"
MARKETPLACE_NAME="claude-plugins-official"

# Nur Plugins ohne externe Dienste (Regel 1 in CLAUDE.md): alles läuft lokal
# im Container, nichts davon schickt Projektdaten nach aussen.
PLUGINS=(
  pyright-lsp           # Typprüfung live, passend zu pyrightconfig.json
  code-review           # /code-review mit spezialisierten Agenten
  commit-commands       # /commit, /commit-push-pr, /clean_gone
  claude-md-management  # CLAUDE.md pflegen
  security-guidance     # Sicherheitshinweise beim Bearbeiten
  frontend-design       # Oberfläche, passend zu Vanilla JS/CSS
  playwright            # Browsersteuerung; Chromium ist vorinstalliert
)

claude plugin marketplace add "$MARKETPLACE_REPO" \
  || claude plugin marketplace update "$MARKETPLACE_NAME" \
  || true

for plugin in "${PLUGINS[@]}"; do
  claude plugin install "${plugin}@${MARKETPLACE_NAME}" || true
done

claude plugin list || true

exit 0
