"""queue

Revision ID: 1e090f33bab
Revises: bea3ba88c73
Create Date: 2015-06-01 15:36:31.935968

"""

# revision identifiers, used by Alembic.
revision = '1e090f33bab'
down_revision = 'bea3ba88c73'

from alembic import op
import sqlalchemy as sa
# from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        'queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dc', sa.String(), nullable=True),
        sa.Column('vm', sa.String(), nullable=True),
        sa.Column('platform', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('queue')