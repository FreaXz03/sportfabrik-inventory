"""users.language (i18n Phase A Punkt 2): DE/FR/EN, Deutsch als Standard."""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column(
                'language',
                sa.String(2),
                nullable=False,
                server_default=sa.text("'de'"),
            )
        )
        batch_op.create_check_constraint(
            'ck_users_language', "language IN ('de', 'fr', 'en')"
        )


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_users_language', type_='check')
        batch_op.drop_column('language')
