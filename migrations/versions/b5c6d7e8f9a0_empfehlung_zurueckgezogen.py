"""Empfehlung der Zentrale zurückziehen (Entscheid 30.09.2026).

Neuer Status `zurueckgezogen` für eine Empfehlung der Zentrale, dazu wer und
wann (beide Spalten leer). Die Zentrale darf jederzeit zurückziehen, auch
nach der Antwort der Filiale; eine schon gesetzte Stufe bleibt. Bestehende
Zeilen bleiben, wie sie sind.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b5c6d7e8f9a0'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reduktion_empfehlung_zentrale') as batch_op:
        batch_op.add_column(sa.Column('zurueckgezogen_von_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('zurueckgezogen_am', sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_constraint('ck_empfehlung_zentrale_status', type_='check')
        batch_op.create_check_constraint(
            'ck_empfehlung_zentrale_status',
            "status IN ('offen', 'uebernommen', 'abgelehnt', 'zurueckgezogen')",
        )


def downgrade():
    # Ohne den Status gilt eine zurückgezogene Empfehlung als abgelehnt - sie
    # ist ohnehin nicht mehr offen.
    op.execute("UPDATE reduktion_empfehlung_zentrale SET status = 'abgelehnt' WHERE status = 'zurueckgezogen'")
    with op.batch_alter_table('reduktion_empfehlung_zentrale') as batch_op:
        batch_op.drop_constraint('ck_empfehlung_zentrale_status', type_='check')
        batch_op.create_check_constraint(
            'ck_empfehlung_zentrale_status', "status IN ('offen', 'uebernommen', 'abgelehnt')"
        )
        batch_op.drop_column('zurueckgezogen_am')
        batch_op.drop_column('zurueckgezogen_von_name')
