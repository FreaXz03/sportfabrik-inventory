"""Schnellzugriffe je Benutzer (Punkt 14, Entscheid 24.09.2026).

Eine Spalte am Benutzer für die gewählten Funktionen und ihre Reihenfolge
(app/core/schnellzugriffe.py). Bestehende Konten starten mit NULL, das die
bisherige feste Voreinstellung von fünf Schnellzugriffen ergibt.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('schnellzugriffe', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('schnellzugriffe')
