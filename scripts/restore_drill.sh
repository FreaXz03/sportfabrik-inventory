#!/usr/bin/env bash
# Restore drill: restore a backup into a throwaway PostgreSQL container, never
# into the live database, and check it (package 3, acceptance "one demonstrated
# full restore"). NOT yet run on a real server - see docs/ausfallsicherheit.md.
#
#   scripts/restore_drill.sh                          # newest local backup
#   scripts/restore_drill.sh backups/automatic/inventory-2026...Z
#   scripts/restore_drill.sh /media/usb/inventory-2026...Z.tar.age --key /path/to/sportfabrik-backup-key.txt
#
# Checks: archive readable, pg_restore without errors, schema version present,
# row counts, bestand = sum(lagerbewegungen) for every variant and branch
# (hard rule 2), PDF archive intact. Exit 0 only if everything passed.
set -euo pipefail

IMAGE="${POSTGRES_IMAGE:-postgres:18}"
NAME="sportfabrik-restore-drill-$$"
SOURCE=""
KEY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) SOURCE="$1"; shift ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

if [ -z "$SOURCE" ]; then
  SOURCE="$(find "$ROOT/backups/automatic" -maxdepth 1 -type d -name 'inventory-*' | sort | tail -1)"
  [ -n "$SOURCE" ] || { echo "FEHLER: kein lokales Backup gefunden" >&2; exit 1; }
fi

case "$SOURCE" in
  *.tar.age)
    [ -n "$KEY" ] || { echo "FEHLER: für .tar.age wird --key <privater age-Schlüssel> gebraucht" >&2; exit 1; }
    [ ! -f "$SOURCE.sha256" ] || (cd "$(dirname "$SOURCE")" && sha256sum -c "$(basename "$SOURCE").sha256")
    age -d -i "$KEY" -o "$WORK/backup.tar" "$SOURCE"
    tar -xf "$WORK/backup.tar" -C "$WORK"
    FOLDER="$(find "$WORK" -maxdepth 1 -type d -name 'inventory-*' | head -1)"
    ;;
  *) FOLDER="$SOURCE" ;;
esac
[ -f "$FOLDER/database.dump" ] || { echo "FEHLER: $FOLDER/database.dump fehlt" >&2; exit 1; }
echo "Backup: $FOLDER"

# 1. checksums from the manifest
python3 - "$FOLDER" <<'PY'
import hashlib, json, sys
from pathlib import Path
folder = Path(sys.argv[1])
manifest = json.loads((folder / "manifest.json").read_text())
for name, expected in manifest["sha256"].items():
    digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    if digest != expected:
        sys.exit(f"FEHLER: Prüfsumme von {name} stimmt nicht")
print("Prüfsummen laut manifest.json: OK")
PY

# 2. PDF archive
python3 - "$FOLDER/original-pdfs.zip" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    bad = z.testzip()
    if bad:
        sys.exit(f"FEHLER: beschädigte Datei im PDF-Archiv: {bad}")
    print(f"PDF-Archiv: {len(z.namelist())} Datei(en), CRC OK")
PY

# 3. throwaway database (no published port, removed on exit)
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=drill "$IMAGE" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U postgres -d drill >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$NAME" pg_isready -U postgres -d drill >/dev/null

docker exec -i "$NAME" pg_restore -U postgres -d drill --no-owner --exit-on-error < "$FOLDER/database.dump"
echo "pg_restore: OK"

sql() { docker exec "$NAME" psql -U postgres -d drill -At -c "$1"; }

echo "Schema-Version (alembic): $(sql 'select version_num from alembic_version')"
for tabelle in artikel varianten dokumente wareneingaenge wareneingang_positionen lagerbewegungen bestand zaehlungen users; do
  echo "  $tabelle: $(sql "select count(*) from $tabelle")"
done

abweichungen="$(sql "
  select count(*) from (
    select coalesce(b.varianten_id, m.varianten_id) as v, coalesce(b.lagerort_id, m.lagerort_id) as l,
           coalesce(b.menge, 0) as bestand, coalesce(m.summe, 0) as summe
    from bestand b
    full outer join (select varianten_id, lagerort_id, sum(menge) as summe
                     from lagerbewegungen group by varianten_id, lagerort_id) m
      on m.varianten_id = b.varianten_id and m.lagerort_id = b.lagerort_id
  ) t where bestand <> summe")"
echo "Bestand ≠ Summe der Lagerbewegungen: $abweichungen Zeile(n)"
[ "$abweichungen" = "0" ] || { echo "FEHLER: Bestand passt nicht zum Journal" >&2; exit 1; }

echo "RESTORE-DRILL BESTANDEN: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
