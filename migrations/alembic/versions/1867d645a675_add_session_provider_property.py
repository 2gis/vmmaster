from alembic import op
import sqlalchemy as sa


"""add session provider property

Revision ID: 1867d645a675
Revises: 2c579499c3aa
Create Date: 2017-11-14 15:09:23.752336

"""

# revision identifiers, used by Alembic.
revision = '1867d645a675'
down_revision = '2c579499c3aa'


def upgrade():
    op.add_column('sessions', sa.Column(
        'provider_id', sa.Integer(), nullable=True))


def downgrade():
    raise NotImplemented
