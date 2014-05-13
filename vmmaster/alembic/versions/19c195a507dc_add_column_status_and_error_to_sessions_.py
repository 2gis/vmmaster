"""add column status and error to sessions table

Revision ID: 19c195a507dc
Revises: None
Create Date: 2014-05-14 16:32:45.604030

"""

# revision identifiers, used by Alembic.
revision = '19c195a507dc'
down_revision = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('sessions', sa.Column('status', sa.Enum('unknown', 'running', 'succeed', 'failed', name='status', native_enum=False)))
    op.add_column('sessions', sa.Column('error', sa.String))


def downgrade():
    op.drop_column('sessions', 'status')
    op.drop_column('sessions', 'error')
