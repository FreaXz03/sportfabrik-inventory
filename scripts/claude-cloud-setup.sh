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

install_marketplace() {
  local repo="$1" name="$2"
  shift 2
  claude plugin marketplace add "$repo" \
    || claude plugin marketplace update "$name" \
    || true
  local plugin
  for plugin in "$@"; do
    claude plugin install "${plugin}@${name}" || true
  done
}

# Offizieller Marktplatz von Anthropic.
install_marketplace anthropics/claude-plugins-official claude-plugins-official \
  pyright-lsp \
  code-review \
  commit-commands \
  claude-md-management \
  security-guidance \
  frontend-design \
  playwright \
  context7

# Marktplatz von thedotmack; von dort wird nur claude-mem installiert.
install_marketplace thedotmack/claude-mem thedotmack \
  claude-mem

# Hinweis: context7 und claude-mem fragen externe Dienste an (Kontext-
# Dokumentation bzw. cmem.ai). Sie sind eine bewusste, ausdrücklich gewünschte
# Ausnahme von Regel 1 in CLAUDE.md — siehe docs/claude-cloud-setup.md.

claude plugin list || true

exit 0
