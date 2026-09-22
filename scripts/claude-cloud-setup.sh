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

# Fabians eigener Marktplatz: bündelt die offiziellen Plugins und die aus
# fremden Repos an einer Stelle. Er und die dort verlinkten Quell-Repos müssen
# öffentlich sein — der Container hat keine Git-Anmeldedaten für fremde Repos.
MARKETPLACE_REPO="FreaXz03/claude-plugin-marketplace"
MARKETPLACE_NAME="claude-plugin-marketplace"

# Nicht dabei, obwohl im Marktplatz gelistet:
#   obsidian       — der Vault liegt auf dem Arbeitsrechner
#   security-sweep — das Quell-Repo onomeaj/security-sweep-plugin ist nicht
#                    anonym klonbar; siehe docs/claude-cloud-setup.md
PLUGINS=(
  pyright-lsp           # Typprüfung live, passend zu pyrightconfig.json
  code-review           # /code-review mit spezialisierten Agenten
  commit-commands       # /commit, /commit-push-pr, /clean_gone
  claude-md-management  # CLAUDE.md pflegen
  security-guidance     # Sicherheitshinweise beim Bearbeiten
  frontend-design       # Oberfläche, passend zu Vanilla JS/CSS
  playwright            # Browsersteuerung; Chromium ist vorinstalliert
  markitdown            # Dokumente nach Markdown wandeln
  caveman               # knappe Antworten
  context-mode          # Kontextfenster schonen
  context7              # Bibliotheks-Dokumentation zur Hand
  claude-mem            # Gedächtnis über Sessions hinweg
)

claude plugin marketplace add "$MARKETPLACE_REPO" \
  || claude plugin marketplace update "$MARKETPLACE_NAME" \
  || true

for plugin in "${PLUGINS[@]}"; do
  claude plugin install "${plugin}@${MARKETPLACE_NAME}" || true
done

# Hinweis: context7 und claude-mem sprechen mit externen Diensten. Regel 1
# verlangt lokale Verarbeitung für Belegdaten — wer in einer Session mit echten
# Rechnungen aus uploads/ arbeitet, schaltet claude-mem vorher ab.

claude plugin list || true

exit 0
