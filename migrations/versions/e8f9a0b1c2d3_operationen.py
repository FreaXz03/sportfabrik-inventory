"""Schutz vor doppelter Buchung bei Wiederholung (Entscheid 01.10.2026).

Neue Tabelle `operationen`: je bewusster Aktion eine vom Gerät erzeugte ID mit
der gespeicherten Antwort. Wiederholt das Gerät dieselbe Aktion (Antwort
verloren), kommt die gespeicherte Antwort zurück und es wird nichts doppelt
gebucht. Bestehende Daten bleiben unverändert.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'operationen',
        sa.Column('operation_id', sa.String(length=64), primary_key=True),
        sa.Column('endpunkt', sa.String(length=40), nullable=False),
        sa.Column('kassennummer', sa.String(length=20), nullable=True),
        sa.Column('anfrage_hash', sa.String(length=64), nullable=False),
        sa.Column('antwort', sa.JSON(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_operationen_erstellt_am', 'operationen', ['erstellt_am'])


def downgrade():
    # Es sind nur Wiederholungsschlüssel, keine Geschäftsdaten.
    op.drop_index('ix_operationen_erstellt_am', table_name='operationen')
    op.drop_table('operationen')
