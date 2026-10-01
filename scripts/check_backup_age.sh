#!/usr/bin/env bash
# Fails (exit 1) if the newest local backup is missing or older than MAX_HOURS
# (default 26). Run by the sportfabrik-checks timer; a failing run shows up in
# `systemctl --failed` and `journalctl -u sportfabrik-checks`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="${BACKUP_DIR:-$ROOT/backups/automatic}"
MAX_HOURS="${MAX_HOURS:-26}"

newest="$(find "$DIR" -maxdepth 2 -name manifest.json -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 || true)"
if [ -z "$newest" ]; then
  echo "FEHLER: kein Backup in $DIR" >&2
  exit 1
fi
stamp="${newest%% *}"
file="${newest#* }"
age_hours=$(( ( $(date +%s) - ${stamp%.*} ) / 3600 ))
if [ "$age_hours" -ge "$MAX_HOURS" ]; then
  echo "FEHLER: neuestes Backup ist ${age_hours} h alt (Grenze ${MAX_HOURS} h): $file" >&2
  exit 1
fi
echo "OK: neuestes Backup ${age_hours} h alt: $file"
