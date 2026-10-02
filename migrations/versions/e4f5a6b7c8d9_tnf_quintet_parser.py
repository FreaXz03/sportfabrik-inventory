"""The North Face liest Quintet-Bestellinformationen (02.10.2026).

Der Lieferant „The North Face" (Gruppe Intern, Etikett-Code 444) besteht seit
f2a3b4c5d6e7, bisher ohne Parser. Das Modul `app/services/parsers/quintet.py`
liest die Quintet-24-Bestellinformation; damit der Import den Lieferanten
findet, bekommt er den passenden `parser_key`. Nur Daten, kein Schema.
tests/test_betrieb.py prueft, dass das zu LIEFERANTEN_SEED passt.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None

PARSER_KEYS = {"The North Face": "quintet"}


def upgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    for name, key in PARSER_KEYS.items():
        connection.execute(
            sa.text(
                "UPDATE lieferanten SET parser_key = :key "
                "WHERE name = :name AND parser_key IS NULL"
            ),
            {"name": name, "key": key},
        )


def downgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    for name, key in PARSER_KEYS.items():
        connection.execute(
            sa.text(
                "UPDATE lieferanten SET parser_key = NULL "
                "WHERE name = :name AND parser_key = :key"
            ),
            {"name": name, "key": key},
        )
