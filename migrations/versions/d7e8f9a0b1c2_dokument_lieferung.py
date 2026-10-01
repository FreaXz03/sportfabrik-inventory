"""Dokumente an eine bestehende Lieferung hängen (Entscheid 01.10.2026).

Neue Tabelle `dokument_lieferung`: ein Lieferschein oder eine Rechnung zur
selben Ware wie ein bestehender Wareneingang bucht nichts, sondern hängt an
diesem Wareneingang. Bestehende Daten bleiben unverändert.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd7e8f9a0b1c2'
down_revision = 'c6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dokument_lieferung',
        sa.Column('dokument_id', sa.Integer(), sa.ForeignKey('dokumente.id'), primary_key=True),
        sa.Column('wareneingang_id', sa.Integer(), sa.ForeignKey('wareneingaenge.id'), nullable=False),
    )
    op.create_index('ix_dokument_lieferung_wareneingang_id', 'dokument_lieferung', ['wareneingang_id'])


def downgrade():
    # Die angehängten Dokumente bleiben als eigenständige Dokumente ohne Ware
    # bestehen; nur die Zuordnung zur Lieferung geht verloren.
    op.drop_index('ix_dokument_lieferung_wareneingang_id', table_name='dokument_lieferung')
    op.drop_table('dokument_lieferung')
