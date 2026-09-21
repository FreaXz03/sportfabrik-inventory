"""Manuelle Erfassung: Wareneingang ohne Beleg, Artikel ohne Lieferant
(Phase B, Teilaufgabe B6).

D27: Ware ohne Dokument ist ein **direkter Wareneingang ohne Beleg** - es
entsteht kein Eintrag in `dokumente`. Dafuer muss `wareneingaenge.dokument_id`
leer bleiben duerfen.

D23: Pflicht sind nur Marke, Bezeichnung, Menge und UVP. Der Lieferant ist
optional, also muss auch `artikel.lieferant_id` leer bleiben duerfen - bisher
kam jeder Artikel aus einem Lieferantendokument und hatte zwangslaeufig einen.

Beide Spalten werden nur nullable gemacht; bestehende Daten bleiben unberuehrt
(sie haben ueberall einen Wert). Der Weg zurueck funktioniert nur, solange es
keine belegfreien Wareneingaenge und keine Artikel ohne Lieferant gibt.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.alter_column(
            'dokument_id', existing_type=sa.Integer(), nullable=True
        )
    with op.batch_alter_table('artikel') as batch_op:
        batch_op.alter_column(
            'lieferant_id', existing_type=sa.Integer(), nullable=True
        )


def downgrade():
    with op.batch_alter_table('artikel') as batch_op:
        batch_op.alter_column(
            'lieferant_id', existing_type=sa.Integer(), nullable=False
        )
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.alter_column(
            'dokument_id', existing_type=sa.Integer(), nullable=False
        )
