"""Allow an explicitly linked replacement of a cancelled document.

Active duplicates remain prohibited by partial unique indexes. Cancelled
records, source data and movements are retained without renaming or deletion.
"""
from alembic import op, context
import sqlalchemy as sa
revision='a20261028'
down_revision='e0f1a2b3c4d5'
branch_labels=None
depends_on=None


def upgrade():
    conn=op.get_bind()
    if context.is_offline_mode():
        # PostgreSQL names the original unnamed hash constraint this way.
        constraints = [
            {'name': 'dokumente_datei_hash_key', 'column_names': ['datei_hash']},
            {'name': 'uq_dokumente_lieferant_dokumentnummer',
             'column_names': ['lieferant_id', 'dokumentnummer']},
        ]
    else:
        constraints=sa.inspect(conn).get_unique_constraints('dokumente')
    with op.batch_alter_table('dokumente',naming_convention={'uq':'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        for constraint in constraints:
            if constraint['column_names'] in (['datei_hash'],['lieferant_id','dokumentnummer']):
                name=constraint['name'] or 'uq_dokumente_'+constraint['column_names'][0]
                batch.drop_constraint(name,type_='unique')
        batch.add_column(sa.Column('ersetzt_dokument_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_dokumente_ersetzt','dokumente',['ersetzt_dokument_id'],['id'])
    for name,cols in [('uq_dokumente_active_number',['lieferant_id','dokumentnummer']),
                      ('uq_dokumente_active_hash',['datei_hash'])]:
        op.create_index(name,'dokumente',cols,unique=True,
                        postgresql_where=sa.text("status = 'aktiv'"),sqlite_where=sa.text("status = 'aktiv'"))


def downgrade():
    # Deliberately fails rather than deleting history if replacements exist.
    with op.batch_alter_table('dokumente') as batch:
        batch.create_unique_constraint('dokumente_datei_hash_key',['datei_hash'])
        batch.create_unique_constraint('uq_dokumente_lieferant_dokumentnummer',['lieferant_id','dokumentnummer'])
        batch.drop_constraint('fk_dokumente_ersetzt',type_='foreignkey')
        batch.drop_column('ersetzt_dokument_id')
    op.drop_index('uq_dokumente_active_number',table_name='dokumente')
    op.drop_index('uq_dokumente_active_hash',table_name='dokumente')
