"""Gezählte Mengen festhalten, auch ohne Differenz (Entscheid 01.10.2026).

Neue Tabelle `zaehlungen`: jede Zählung mit Bestand vorher, gezählter Menge
und Differenz. Eine Zählung ohne Differenz hat keine Lagerbewegung, ist aber
als „gezählt, kein Unterschied" nachweisbar. Bestehende Daten bleiben
unverändert (frühere Zählungen sind nur als Korrektur-Bewegungen vorhanden).
"""
from alembic import op
import sqlalchemy as sa

revision = 'f9a0b1c2d3e4'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'zaehlungen',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('gezaehlt', sa.Numeric(10, 2), nullable=False),
        sa.Column('bestand_vorher', sa.Numeric(10, 2), nullable=False),
        sa.Column('differenz', sa.Numeric(10, 2), nullable=False),
        sa.Column('grund', sa.String(length=200), nullable=True),
        sa.Column('bewegung_id', sa.Integer(), sa.ForeignKey('lagerbewegungen.id'), nullable=True),
        sa.Column(
            'bestaetigt_trotz_aenderung', sa.Boolean(), nullable=False, server_default=sa.text('false')
        ),
        sa.Column('benutzer_kassennummer', sa.String(length=20), nullable=True),
        sa.Column('benutzer_name', sa.String(length=100), nullable=True),
        sa.Column('zeitpunkt', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_zaehlungen_lagerort_id', 'zaehlungen', ['lagerort_id'])
    op.create_index('ix_zaehlungen_varianten_id', 'zaehlungen', ['varianten_id'])


def downgrade():
    # Die Nachweise der Zählungen ohne Differenz gehen verloren; Bestand und
    # Lagerbewegungen bleiben unberührt.
    op.drop_index('ix_zaehlungen_varianten_id', table_name='zaehlungen')
    op.drop_index('ix_zaehlungen_lagerort_id', table_name='zaehlungen')
    op.drop_table('zaehlungen')
