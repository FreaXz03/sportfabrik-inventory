"""Login-Sperre nach zu vielen Fehlversuchen (Sicherheit S2, 24.09.2026).

Zwei Spalten am Benutzer: gezählte falsche Passwörter und Sperre bis. Nach 5
Fehlversuchen ist ein Konto 20 Minuten gesperrt (app/services/anmeldung.py).
Bestehende Konten starten mit 0 Fehlversuchen und ohne Sperre.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('fehlversuche', sa.Integer(), nullable=False, server_default=sa.text('0'))
        )
        batch_op.add_column(sa.Column('gesperrt_bis', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('gesperrt_bis')
        batch_op.drop_column('fehlversuche')
