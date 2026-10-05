"""Package 4b (05.10.2026): explicit outcomes for the open remainder of a delivery.

* New table `lieferung_differenzen` (in_klaerung | verloren | lieferant_storniert).
* New status `abgeschlossen` for `wareneingaenge`: nothing open any more, but at
  least one remainder was declared lost or cancelled by the supplier.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e0f1a2b3c4d5'
down_revision = 'd9e0f1a2b3c4'
branch_labels = None
depends_on = None

_STATUS_ALT = "status IN ('erwartet', 'eingetroffen', 'storniert')"
_STATUS_NEU = "status IN ('erwartet', 'eingetroffen', 'storniert', 'abgeschlossen')"


def upgrade():
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.drop_constraint('ck_wareneingaenge_status', type_='check')
        batch_op.create_check_constraint('ck_wareneingaenge_status', _STATUS_NEU)
    op.create_table(
        'lieferung_differenzen',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'wareneingang_position_id', sa.Integer(),
            sa.ForeignKey('wareneingang_positionen.id'), nullable=False,
        ),
        sa.Column('art', sa.String(length=20), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('notiz', sa.String(length=200), nullable=True),
        sa.Column('benutzer_kassennummer', sa.String(length=20), nullable=True),
        sa.Column('benutzer_name', sa.String(length=100), nullable=True),
        sa.Column('zeitpunkt', sa.DateTime(timezone=True), nullable=False),
        sa.Column('aufgeloest_am', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "art IN ('in_klaerung', 'verloren', 'lieferant_storniert')",
            name='ck_lieferung_differenzen_art',
        ),
    )
    op.create_index(
        'ix_lieferung_differenzen_wareneingang_position_id',
        'lieferung_differenzen', ['wareneingang_position_id'],
    )


def downgrade():
    # Nie verwerfen: gibt es schon Differenzen oder abgeschlossene Lieferungen,
    # bricht das Zurueckrollen ab.
    verbindung = op.get_bind()
    belegt = verbindung.scalar(
        sa.text(
            "SELECT 1 WHERE EXISTS (SELECT 1 FROM lieferung_differenzen) "
            "OR EXISTS (SELECT 1 FROM wareneingaenge WHERE status = 'abgeschlossen')"
        )
    )
    if belegt:
        raise RuntimeError("Lieferungsdifferenzen vorhanden - Downgrade abgebrochen.")
    op.drop_index('ix_lieferung_differenzen_wareneingang_position_id', table_name='lieferung_differenzen')
    op.drop_table('lieferung_differenzen')
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.drop_constraint('ck_wareneingaenge_status', type_='check')
        batch_op.create_check_constraint('ck_wareneingaenge_status', _STATUS_ALT)
