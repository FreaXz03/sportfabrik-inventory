"""Mehrere EANs je Variante (Punkt 8, 01.10.2026).

Neue Tabelle `varianten_eans` für weitere EANs neben der Hauptnummer
`varianten.ean` (z. B. Original-EAN neben der internen). Jede führt zur selben
Variante; eine EAN gehört nie zu zwei Varianten (eindeutig hier, gegen
`varianten.ean` prüft der Dienst). Bestehende Daten bleiben unverändert.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'varianten_eans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('ean', sa.String(length=30), nullable=False),
        sa.Column('ean_intern', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('angelegt', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_varianten_eans_varianten_id', 'varianten_eans', ['varianten_id'])
    op.create_index('ix_varianten_eans_ean', 'varianten_eans', ['ean'], unique=True)


def downgrade():
    # Die weiteren EANs gehen verloren; Hauptnummern und Bestand bleiben.
    op.drop_index('ix_varianten_eans_ean', table_name='varianten_eans')
    op.drop_index('ix_varianten_eans_varianten_id', table_name='varianten_eans')
    op.drop_table('varianten_eans')
