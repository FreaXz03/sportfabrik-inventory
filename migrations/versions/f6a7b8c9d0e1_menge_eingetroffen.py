"""Erwartet → eingetroffen: tatsaechlich angekommene Menge je Position
(Phase B, Teilaufgabe B5).

Regel 3/D6: Auftragsbestaetigungen und Bestellungen erzeugen nur einen
*erwarteten* Wareneingang; Bestand entsteht erst, wenn die Ware da ist. D22:
Kommt weniger an als erwartet, bleibt die Restmenge offen.

Dafuer braucht jede Position neben der erwarteten Menge (`menge`, so wie sie
auf dem Beleg steht) die bereits eingetroffene: `menge_eingetroffen`. Der
Rest ergibt sich als Differenz, und der Wareneingang gilt erst als
`eingetroffen`, wenn keine Position mehr offen ist.

Altdaten: Alle bisherigen Wareneingaenge stammen aus Rechnungen und wurden
sofort gebucht (Status `eingetroffen`) - ihre Positionen sind also
vollstaendig angekommen.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'wareneingang_positionen',
        sa.Column(
            'menge_eingetroffen',
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text('0'),
        ),
    )
    op.execute(
        "UPDATE wareneingang_positionen SET menge_eingetroffen = COALESCE(menge, 0) "
        "WHERE wareneingang_id IN "
        "(SELECT id FROM wareneingaenge WHERE status = 'eingetroffen')"
    )


def downgrade():
    with op.batch_alter_table('wareneingang_positionen') as batch_op:
        batch_op.drop_column('menge_eingetroffen')
