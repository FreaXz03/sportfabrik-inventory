"""Kategorie von Hand gewaehlt (Phase B, Teilaufgabe B8).

Der FEDAS-Code auf den Lieferantenrechnungen schlaegt die Kassenkategorie
automatisch vor (`app/core/fedas.py`). Fehlt er oder ist er unbekannt, waehlt
sie jemand im Laden von Hand - und **diese** Wahl ist verbindlich: sie darf
von keinem spaeteren Vorschlag ueberschrieben werden ("einmal pro Artikel,
danach gemerkt", siehe Roadmap Abschnitt 6).

Dafuer merkt sich `artikel.kategorie_manuell`, woher die Kategorie stammt:
`false` = Vorschlag aus dem FEDAS-Code, `true` = von Hand gewaehlt. Bestehende
Artikel haben ihre Kategorie ausschliesslich ueber den FEDAS-Vorschlag
bekommen (eine Auswahl-Oberflaeche gab es bis jetzt nicht), also ist `false`
fuer sie der richtige Wert - genau das setzt der Server-Default.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('artikel') as batch_op:
        batch_op.add_column(
            sa.Column(
                'kategorie_manuell',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'),
            )
        )


def downgrade():
    with op.batch_alter_table('artikel') as batch_op:
        batch_op.drop_column('kategorie_manuell')
