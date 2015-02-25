"""add column status and error to sessions table

Revision ID: 19c195a507dc
Revises: 18c195a507dc
Create Date: 2014-05-14 16:32:45.604030

"""

# revision identifiers, used by Alembic.
revision = '19c195a507dc'
down_revision = '18c195a507dc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('sessions', sa.Column('status', sa.Enum('unknown', 'running', 'succeed', 'failed', name='status',
                                                          native_enum=False)))
    op.add_column('sessions', sa.Column('error', sa.String))


def downgrade():
    # FIXME: sqlite not supported column drop
    op.drop_column('sessions', 'status')
    op.drop_column('sessions', 'error')
