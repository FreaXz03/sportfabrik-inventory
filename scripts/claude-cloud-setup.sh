#!/bin/bash
# Setup-Skript für Claude-Code-Cloud-Sessions.
# Einzutragen unter claude.ai/code → Umgebungs-Wähler → Zahnrad → "Setup script".
#
# Läuft einmal pro Umgebung, bevor Claude Code startet; danach wird das
# Dateisystem als Abbild gespeichert und spätere Sessions überspringen das
# Skript. Das Abbild hält **Dateien, keine Prozesse** — laufende Dienste starten
# je Session im SessionStart-Hook (scripts/claude-session-deps.sh).
#
# Plugins gehören genau hierhin: eine Cloud-Session installiert die in
# .claude/settings.json deklarierten Plugins nicht, und was erst während des
# Sessionstarts installiert wird, ist in derselben Session noch nicht geladen.
# Details: docs/claude-cloud-setup.md
#
# Das Skript muss mit 0 enden, sonst startet die Session nicht.

set -uo pipefail

# --- Systempakete: PostgreSQL und Tesseract (DE/FR) für OCR -----------------
apt-get update -qq || true
apt-get install -y -qq postgresql tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra || true

# --- Test-Datenbank anlegen -------------------------------------------------
# Die Daten landen im Abbild und sind in jeder späteren Session vorhanden;
# gestartet werden muss der Dienst trotzdem je Session (siehe Hook oben).
service postgresql start || true
su postgres -c "psql -c \"CREATE USER sportfabrik WITH PASSWORD 'devpass' SUPERUSER;\"" || true
su postgres -c "createdb -O sportfabrik sportfabrik_dev" || true

# --- Claude-Code-Plugins ----------------------------------------------------
# Eigener Marktplatz; er und die dort verlinkten Quell-Repos müssen öffentlich
# sein, der Container hat keine Git-Anmeldedaten für fremde Repos.
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

# Die Python-Abhängigkeiten stehen bewusst NICHT hier: an dieser Stelle
# scheitert "pip install -r requirements.txt" am Debian-Paket PyYAML, das pip
# nicht ersetzen darf. Sie kommen über scripts/claude-session-deps.sh in ein
# .venv, das auch pyrightconfig.json erwartet.

exit 0
