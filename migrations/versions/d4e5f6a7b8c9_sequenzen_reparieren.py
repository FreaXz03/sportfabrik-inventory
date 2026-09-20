"""Id-Sequenzen der neuen Tabellen auf MAX(id) setzen (Reparatur).

Migration c3d4e5f6a7b8 hat die Seed-Daten (`lieferanten`, `kategorien`) mit
expliziten Ids eingefuegt, die Postgres-Sequenzen aber nur dann nachgezogen,
wenn es auch Altdaten zu migrieren gab. Auf einer frischen Datenbank blieben
sie deshalb auf 1 stehen - der erste id-lose Insert (z.B. ein weiterer
Lieferant oder `seed_kategorien()`) scheitert dann mit "duplicate key value
violates unique constraint".

c3d4e5f6a7b8 ist inzwischen korrigiert; diese Migration repariert Datenbanken,
auf denen die fehlerhafte Fassung bereits gelaufen ist. Sie ist idempotent und
auf einer bereits korrekten Datenbank ein No-Op (setval auf denselben Wert).
SQLite vergibt Ids aus MAX(id)+1 und braucht das nicht.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

# Feste Liste, keine Nutzereingabe - siehe _TABELLEN-Verwendung unten.
_TABELLEN = [
    "lieferanten", "kategorien", "artikel", "varianten", "preise",
    "dokumente", "wareneingaenge", "wareneingang_positionen", "lagerbewegungen",
]


def upgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    for tabelle in _TABELLEN:
        # is_called = false bei leerer Tabelle, damit nextval() bei 1 startet.
        connection.execute(
            sa.text(
                f"SELECT setval("
                f"  pg_get_serial_sequence('{tabelle}', 'id'),"
                f"  COALESCE((SELECT MAX(id) FROM {tabelle}), 1),"
                f"  (SELECT MAX(id) FROM {tabelle}) IS NOT NULL"
                f")"
            )
        )


def downgrade():
    # Sequenzstaende sind kein Schema - es gibt nichts sinnvoll zurueckzunehmen.
    pass
