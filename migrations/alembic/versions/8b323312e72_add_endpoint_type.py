from alembic import op
import sqlalchemy as sa

"""add_endpoint_type

Revision ID: 8b323312e72
Revises: cabd23253cb
Create Date: 2017-10-17 13:37:27.029155

"""

# revision identifiers, used by Alembic.
revision = '8b323312e72'
down_revision = 'cabd23253cb'


def upgrade():
    op.add_column('endpoints', sa.Column('endpoint_type', sa.String(length=20)))


def downgrade():
    raise NotImplemented
