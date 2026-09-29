"""Umlagerung unterwegs stornieren (Entscheid 29.09.2026).

Neuer Status `storniert` für einen erwarteten Wareneingang aus einer
Umlagerung: der noch offene Rest ist an die Quelle zurückgebucht, ein schon
angekommener Teil bleibt am Ziel. Nur die Check-Constraint wird erweitert;
bestehende Zeilen bleiben, wie sie sind.
"""
from alembic import op

revision = 'a4b5c6d7e8f9'
down_revision = 'f3a4b5c6d7e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.drop_constraint('ck_wareneingaenge_status', type_='check')
        batch_op.create_check_constraint(
            'ck_wareneingaenge_status', "status IN ('erwartet', 'eingetroffen', 'storniert')"
        )


def downgrade():
    # Ohne den Status gilt eine stornierte Umlagerung als abgeschlossen - sie
    # ist ohnehin nicht mehr offen, der Bestand stimmt über die Bewegungen.
    op.execute("UPDATE wareneingaenge SET status = 'eingetroffen' WHERE status = 'storniert'")
    with op.batch_alter_table('wareneingaenge') as batch_op:
        batch_op.drop_constraint('ck_wareneingaenge_status', type_='check')
        batch_op.create_check_constraint(
            'ck_wareneingaenge_status', "status IN ('erwartet', 'eingetroffen')"
        )
