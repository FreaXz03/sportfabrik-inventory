"""Article notes with author snapshots and optimistic edit version."""
from alembic import op
import sqlalchemy as sa
revision = 'e901abc23456'
down_revision = 'd567ef887517'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('article_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('body', sa.String(2000), nullable=False),
        sa.Column('author_user_id', sa.Integer(), nullable=False),
        sa.Column('author_name', sa.String(100), nullable=False),
        sa.Column('author_number', sa.String(20), nullable=False),
        sa.Column('updated_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_index('ix_article_notes_product_id', 'article_notes', ['product_id'])


def downgrade():
    op.drop_index('ix_article_notes_product_id', table_name='article_notes')
    op.drop_table('article_notes')
