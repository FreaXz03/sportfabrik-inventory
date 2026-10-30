"""Permanent winter reconciliation audit and superseded expected positions."""
from alembic import op
import sqlalchemy as sa
revision = 'b20261030'
down_revision = 'a20261028'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('winter_abgleiche',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('wareneingang_id',sa.Integer(),sa.ForeignKey('wareneingaenge.id'),nullable=False),
        sa.Column('datei_hash',sa.String(64),nullable=False),
        sa.Column('anfrage_hash',sa.String(64),nullable=False,unique=True),
        sa.Column('dateiname',sa.String(500),nullable=False),
        sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('benutzer_kassennummer',sa.String(20)),
        sa.Column('benutzer_name',sa.String(100)),
        sa.Column('zeitpunkt',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_winter_abgleiche_datei_hash','winter_abgleiche',['datei_hash'])
    op.create_index('ix_winter_abgleiche_wareneingang_id','winter_abgleiche',['wareneingang_id'])
    with op.batch_alter_table('wareneingang_positionen') as batch:
        batch.add_column(sa.Column('ersetzt_durch_abgleich_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_winter_abgleich_position','winter_abgleiche',['ersetzt_durch_abgleich_id'],['id'])


def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM winter_abgleiche')).scalar():
        raise RuntimeError('Cannot remove winter audit after revisions have been applied.')
    with op.batch_alter_table('wareneingang_positionen') as batch:
        batch.drop_constraint('fk_winter_abgleich_position',type_='foreignkey')
        batch.drop_column('ersetzt_durch_abgleich_id')
    op.drop_index('ix_winter_abgleiche_datei_hash',table_name='winter_abgleiche')
    op.drop_index('ix_winter_abgleiche_wareneingang_id',table_name='winter_abgleiche')
    op.drop_table('winter_abgleiche')
