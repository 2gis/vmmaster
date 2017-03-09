"""used property for endpoints

Revision ID: 575ac791bca9
Revises: 175aecf5691f
Create Date: 2017-02-24 19:23:42.208515

"""

# revision identifiers, used by Alembic.
revision = '575ac791bca9'
down_revision = '175aecf5691f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('endpoints', sa.Column('used', sa.Boolean(), default=False))
    op.add_column('endpoints', sa.Column('created_time', sa.DateTime(), default=None))
    op.add_column('endpoints', sa.Column('used_time', sa.DateTime(), default=None))
    op.add_column('endpoints', sa.Column('deleted_time', sa.DateTime(), default=None))
    op.drop_column('endpoints', 'created')


def downgrade():
    op.drop_column('endpoints', 'used')
    op.drop_column('endpoints', 'created_time')
    op.drop_column('endpoints', 'used_time')
    op.drop_column('endpoints', 'deleted_time')
    op.add_column('endpoints', sa.Column('created', sa.Float, nullable=True))
