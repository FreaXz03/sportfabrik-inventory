"""Lieferanten mit eigenem Parser (Phase E, 24.09.2026).

Alpina, Chris Sports und CMP haben jetzt je ein Parser-Modul
(`app/services/parsers/`). Damit der Import sie findet, braucht jeder einen
Lieferanten mit passendem `parser_key`. Alle drei sind Direktbestellungen bei
Marke bzw. Verteiler: Gruppe Dritte-Haendler, Etikett-Code 999 (Fabian,
24.09.2026). Nur Daten, kein Schema. Seed-Daten bewusst literal dupliziert -
siehe a1b2c3d4e5f6; tests/test_betrieb.py prueft, dass beides uebereinstimmt.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None

_NEUE_LIEFERANTEN = [
    {"name": "ALPINA SPORTS Schweiz AG", "typ": "drittanbieter", "parser_key": "alpina"},
    {"name": "CHRIS sports AG", "typ": "drittanbieter", "parser_key": "chrissports"},
    {"name": "CMP (F.lli Campagnolo S.p.A.)", "typ": "drittanbieter", "parser_key": "cmp"},
]


def upgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    vorhanden = set(connection.scalars(sa.text("SELECT name FROM lieferanten")).all())
    for eintrag in _NEUE_LIEFERANTEN:
        if eintrag["name"] not in vorhanden:
            connection.execute(
                sa.text(
                    "INSERT INTO lieferanten (name, typ, parser_key) "
                    "VALUES (:name, :typ, :parser_key)"
                ),
                eintrag,
            )


def downgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    # Nur loeschen, solange nichts daran haengt ("nie verwerfen").
    for eintrag in _NEUE_LIEFERANTEN:
        belegt = connection.scalar(
            sa.text(
                "SELECT 1 FROM lieferanten l WHERE l.name = :name AND ("
                "  EXISTS (SELECT 1 FROM artikel a WHERE a.lieferant_id = l.id)"
                "  OR EXISTS (SELECT 1 FROM dokumente d WHERE d.lieferant_id = l.id))"
            ),
            {"name": eintrag["name"]},
        )
        if not belegt:
            connection.execute(
                sa.text("DELETE FROM lieferanten WHERE name = :name"), {"name": eintrag["name"]}
            )
