"""Gebuchte Dokumente stornieren statt löschen (Entscheid 01.10.2026).

Status `aktiv`/`storniert` am Dokument, dazu wer und wann (leer bei aktiven
Dokumenten). Bestehende Dokumente bleiben `aktiv`.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c6d7e8f9a0b1'
down_revision = 'b5c6d7e8f9a0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('dokumente') as batch_op:
        batch_op.add_column(
            sa.Column('status', sa.String(length=20), nullable=False, server_default='aktiv')
        )
        batch_op.add_column(sa.Column('storniert_am', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column('storniert_von_kassennummer', sa.String(length=20), nullable=True)
        )
        batch_op.add_column(sa.Column('storniert_von_name', sa.String(length=100), nullable=True))
        batch_op.create_check_constraint('ck_dokumente_status', "status IN ('aktiv', 'storniert')")


def downgrade():
    # Ein stornierter Beleg ist nach dem Zurückstufen wieder ein normaler Beleg
    # - seine Gegenbuchungen bleiben im Journal, der Bestand stimmt weiter.
    with op.batch_alter_table('dokumente') as batch_op:
        batch_op.drop_constraint('ck_dokumente_status', type_='check')
        batch_op.drop_column('storniert_von_name')
        batch_op.drop_column('storniert_von_kassennummer')
        batch_op.drop_column('storniert_am')
        batch_op.drop_column('status')
