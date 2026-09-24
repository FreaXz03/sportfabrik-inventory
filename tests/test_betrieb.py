"""Betrieb: Migrationen laufen durch, die Seiten-Skripte sind gültig, der
Login leitet nur auf eigene Seiten weiter, und das Frontend lädt nichts aus
dem Internet (Regel 1: es muss im Ladennetz ohne Internet laufen).

Die Tests mit Node.js werden ohne Node übersprungen.
"""

import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"


def _alembic(*argumente, **env):
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("DB_") and k != "DATABASE_URL"}
    umgebung.update(env)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", *argumente],
        cwd=ROOT, env=umgebung, capture_output=True, timeout=60,
    )


def test_migrationen_offline_fuer_postgres_und_online_auf_sqlite(tmp_path):
    """Offline: SQL für PostgreSQL aus Container-Variablen (Sonderzeichen im
    Passwort). Online: alle Migrationen auf einer leeren Datenbank."""
    offline = _alembic(
        "--sql", DB_HOST="db", DB_PASSWORD="test@pass%with/slash:#", DB_USER="inventory", DB_NAME="inventory_db"
    )
    assert offline.returncode == 0, offline.stderr.decode()
    assert b"CREATE TABLE users" in offline.stdout and b"lagerbewegungen" in offline.stdout

    datei = tmp_path / "migration.db"
    online = _alembic(DATABASE_URL=f"sqlite:///{datei.as_posix()}")
    assert online.returncode == 0, online.stderr.decode()
    with sqlite3.connect(datei) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()
        codes = [row[0] for row in db.execute("SELECT code FROM lagerorte ORDER BY code")]
        assert codes == ["DIETIKON", "GEWA", "SF1", "SF2", "SF3", "SF4", "VEBO"]
        parser = {row[0] for row in db.execute("SELECT parser_key FROM lieferanten WHERE parser_key IS NOT NULL")}
        assert parser == {"intersport", "alpina", "chrissports", "cmp"}


def _skripte_der_seite(html: str) -> list[str]:
    """Alle <script>-Blöcke in Dokumentreihenfolge (eigene Dateien als Inhalt)."""
    skripte = []
    for attribute, inline in re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
        src = re.search(r"""src=["']([^"']+)["']""", attribute)
        if src:
            pfad = src.group(1).split("?")[0]
            if pfad.startswith("/static/js/"):
                skripte.append((ROOT / "app" / pfad.lstrip("/")).read_text("utf-8"))
        elif inline.strip():
            skripte.append(inline)
    return skripte


@pytest.mark.parametrize("seite", sorted(TEMPLATES.glob("*.html")), ids=lambda p: p.name)
def test_seite_ohne_internet_und_mit_gueltigen_skripten(seite):
    """Keine externen Skripte/Stylesheets (Regel 1). Alle Skripte einer Seite
    teilen sich im Browser einen Scope - eine doppelte let/const-Deklaration
    legt sonst lautlos die ganze Seite lahm."""
    html = seite.read_text("utf-8")
    extern = re.findall(r"""<(?:script|link)\b[^>]*(?:src|href)=["'](?:https?:)?//""", html, re.I)
    assert extern == []
    node = shutil.which("node")
    skripte = _skripte_der_seite(html)
    if not node or not skripte:
        pytest.skip("Node.js fehlt oder die Seite hat keine Skripte")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as datei:
        datei.write("\n;\n".join(skripte))
    try:
        ergebnis = subprocess.run([node, "--check", datei.name], capture_output=True, timeout=15)
    finally:
        Path(datei.name).unlink(missing_ok=True)
    assert ergebnis.returncode == 0, ergebnis.stderr.decode()


def test_login_leitet_nur_auf_eigene_seiten_weiter():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js fehlt")
    skript = (ROOT / "app/static/js/login-redirect.js").read_text("utf-8") + r"""
const assert = require('node:assert/strict');
const origin = 'http://localhost:8080';
for (const input of [null, '', 'https://evil.example', '//evil.example',
    '/\\evil.example', 'javascript:alert(1)', '/static/js/theme.js',
    '/login?next=https://evil.example', '/%2f%2fevil.example', '/\tevil.example',
    ' /articles', '/api/invoices', '/unknown']) {
  assert.equal(safeLoginRedirect(input, origin), '/', String(input));
}
for (const input of ['/', '/articles', '/invoices', '/preview',
    '/invoices/123', '/articles/7/history', '/articles?q=Hoka#results']) {
  assert.equal(safeLoginRedirect(input, origin), input);
}
"""
    ergebnis = subprocess.run([node, "-"], input=skript.encode(), capture_output=True, timeout=15)
    assert ergebnis.returncode == 0, ergebnis.stderr.decode()


def _migration(datei):
    spec = importlib.util.spec_from_file_location(datei, ROOT / "migrations" / "versions" / f"{datei}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_datenmigrationen_passen_zu_den_stammdaten():
    """Migrationen, die bestehende Daten umbauen, und die Stammdaten für neue
    Datenbanken dürfen nicht auseinanderlaufen: Filialcodes (F13),
    Lieferantengruppen (23.09.2026) und Lieferanten mit Parser (24.09.2026)."""
    from app.core.lagerorte import LAGERORTE_SEED
    from app.core.lieferanten import LIEFERANTEN_SEED

    filialcodes = _migration("d0e1f2a3b4c5_filialcodes_korrigieren")
    assert filialcodes.RICHTIG == {e["ort"]: e["code"] for e in LAGERORTE_SEED if e["code"] in ("SF2", "SF3", "SF4")}
    gruppen = _migration("f2a3b4c5d6e7_lieferantengruppen")
    parser = _migration("a8b9c0d1e2f3_lieferanten_mit_parser")
    assert [LIEFERANTEN_SEED[0]] + gruppen._NEUE_LIEFERANTEN + parser._NEUE_LIEFERANTEN == LIEFERANTEN_SEED


def test_filialcodes_werden_im_ring_getauscht():
    """SF2 → SF3 → SF4 → SF2 über Zwischencodes (code ist eindeutig); der Ort
    bleibt, damit gebuchte Ware ihre Filiale behält - und zurück."""
    from conftest import neue_datenbank
    from sqlalchemy import delete, select

    from app.core.models import Lagerort

    migration = _migration("d0e1f2a3b4c5_filialcodes_korrigieren")
    vorher = {"Regensdorf": "SF2", "Hägendorf": "SF3", "Conthey": "SF4"}
    with neue_datenbank()() as session:
        session.execute(delete(Lagerort))
        session.add_all(Lagerort(code=code, name=ort, ort=ort) for ort, code in vorher.items())
        session.flush()
        migration._codes_setzen(session.connection(), migration.RICHTIG)
        session.expire_all()
        assert {lo.ort: lo.code for lo in session.scalars(select(Lagerort))} == {
            "Conthey": "SF2", "Regensdorf": "SF3", "Hägendorf": "SF4"
        }
        migration._codes_setzen(session.connection(), migration.VORHER)
        session.expire_all()
        assert {lo.ort: lo.code for lo in session.scalars(select(Lagerort))} == vorher
