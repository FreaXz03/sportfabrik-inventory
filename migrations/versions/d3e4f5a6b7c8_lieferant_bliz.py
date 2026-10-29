"""Lieferant Bliz mit eigenem Parser (02.10.2026).

Bliz hat ein Parser-Modul (`app/services/parsers/bliz.py`). Damit der Import den
Lieferanten findet, braucht er einen Eintrag mit passendem `parser_key`. Wie die
anderen Direktbestellungen bei der Marke: Gruppe Dritte-Haendler, Etikett-Code
999 (angenommen wie Alpina/Chris/CMP). Nur Daten, kein Schema. Seed-Daten bewusst literal dupliziert -
siehe a1b2c3d4e5f6; tests/test_betrieb.py prueft, dass beides uebereinstimmt.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None

_NEUE_LIEFERANTEN = [
    {"name": "Bliz", "typ": "drittanbieter", "parser_key": "bliz"},
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
