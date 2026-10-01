"""Erwartete Lieferung an eine andere Filiale umleiten (Punkt 3, 01.10.2026).

Neue Tabelle `wareneingang_umleitungen`: Historie jeder Umleitung (von, nach,
wer, wann). Die Erwartung selbst wandert über `wareneingaenge.lagerort_id`;
gebucht wird weiterhin erst bei der Ankunft (Regel 3). Bestehende Daten
bleiben unverändert.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wareneingang_umleitungen',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('wareneingang_id', sa.Integer(), sa.ForeignKey('wareneingaenge.id'), nullable=False),
        sa.Column('von_lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('nach_lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('benutzer_kassennummer', sa.String(length=20), nullable=True),
        sa.Column('benutzer_name', sa.String(length=100), nullable=True),
        sa.Column('zeitpunkt', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_wareneingang_umleitungen_wareneingang_id', 'wareneingang_umleitungen', ['wareneingang_id'])


def downgrade():
    # Die Historie geht verloren; Lieferungen bleiben am zuletzt gesetzten Ziel.
    op.drop_index('ix_wareneingang_umleitungen_wareneingang_id', table_name='wareneingang_umleitungen')
    op.drop_table('wareneingang_umleitungen')
