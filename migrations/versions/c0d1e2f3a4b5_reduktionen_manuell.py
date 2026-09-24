"""Manuelle Reduktion je Modell × Filiale (24.09.2026).

Neue Tabelle `reduktionen_manuell`: alle Mitarbeitenden dürfen in ihren
Filialen 30, 50 oder 70 % wählen; ohne Zeile gilt die Empfehlung nach Regel 6.
Keine Altdaten zu migrieren.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c0d1e2f3a4b5'
down_revision = 'b9c0d1e2f3a4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reduktionen_manuell',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('prozent', sa.Integer(), nullable=False),
        sa.Column('benutzer_kassennummer', sa.String(20), nullable=True),
        sa.Column('benutzer_name', sa.String(100), nullable=True),
        sa.Column('gesetzt_am', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('artikel_id', 'lagerort_id', name='uq_reduktionen_manuell_artikel_lagerort'),
        sa.CheckConstraint('prozent IN (30, 50, 70)', name='ck_reduktionen_manuell_prozent'),
    )
    op.create_index('ix_reduktionen_manuell_artikel_id', 'reduktionen_manuell', ['artikel_id'])
    op.create_index('ix_reduktionen_manuell_lagerort_id', 'reduktionen_manuell', ['lagerort_id'])


def downgrade():
    op.drop_index('ix_reduktionen_manuell_lagerort_id', table_name='reduktionen_manuell')
    op.drop_index('ix_reduktionen_manuell_artikel_id', table_name='reduktionen_manuell')
    op.drop_table('reduktionen_manuell')
