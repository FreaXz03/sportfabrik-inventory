"""Lieferant fuer den internen Bestellplan Winter (05.10.2026).

Parser-Modul `app/services/parsers/bestellplan.py`. Die Ware kommt direkt von
Dritt-Lieferanten (Fabian, 05.10.2026): Gruppe Dritte-Haendler, Etikett-Code 999.
Nur Daten, kein Schema. Seed-Daten bewusst literal dupliziert -
siehe a1b2c3d4e5f6; tests/test_betrieb.py prueft, dass beides uebereinstimmt.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'a6b7c8d9e0f1'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None

_NEUE_LIEFERANTEN = [
    {"name": "Bestellplan (Dritte-Händler)", "typ": "drittanbieter", "parser_key": "bestellplan"},
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
