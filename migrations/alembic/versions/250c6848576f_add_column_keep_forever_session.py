"""add column keep_forever session

Revision ID: 250c6848576f
Revises: 4f80a6b3ffc2
Create Date: 2017-08-28 15:25:20.101394

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '250c6848576f'
down_revision = '4f80a6b3ffc2'


def upgrade():
    op.add_column('sessions', sa.Column('keep_forever', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('sessions', 'keep_forever')
