"""Umlagerung wie eine Lieferung (Entscheid 28.09.2026).

Bisher buchte eine Umlagerung Abgang und Zugang in einem Schritt. Neu
versendet die Quelle die Ware mit einem Versanddatum (Abgang sofort), und
das Ziel bekommt einen erwarteten Wareneingang, dessen Ankunft es wie bei
einer Lieferung bestätigt (nach dem Auspacken, D21/D22).

* `wareneingaenge.herkunft_lagerort_id`: gesetzt, wenn der erwartete
  Wareneingang aus einer Umlagerung stammt (sonst leer - Dokument oder
  manuelle Erfassung).
* `wareneingaenge.versanddatum`: der Tag, an dem die Quelle verschickt hat.
* `wareneingang_positionen.mitgebracht_datum`: das Eingangsdatum, das die
  Ware beim Versand an der Quelle hatte (D17: Filiale -> Filiale behält es).

Nur neue, leere Spalten; bestehende Umlagerungen bleiben, wie sie sind.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a4b5c6d7e8'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.add_column(sa.Column('herkunft_lagerort_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('versanddatum', sa.Date(), nullable=True))
        batch_op.create_foreign_key(
            'fk_wareneingaenge_herkunft_lagerort', 'lagerorte', ['herkunft_lagerort_id'], ['id']
        )
    with op.batch_alter_table('wareneingang_positionen') as batch_op:
        batch_op.add_column(sa.Column('mitgebracht_datum', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('wareneingang_positionen') as batch_op:
        batch_op.drop_column('mitgebracht_datum')
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.drop_constraint('fk_wareneingaenge_herkunft_lagerort', type_='foreignkey')
        batch_op.drop_column('versanddatum')
        batch_op.drop_column('herkunft_lagerort_id')
