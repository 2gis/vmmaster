from alembic import op
import sqlalchemy as sa


"""add provider max limit property

Revision ID: 3332aa012b73
Revises: 1867d645a675
Create Date: 2017-11-14 18:21:31.292431

"""

# revision identifiers, used by Alembic.
revision = '3332aa012b73'
down_revision = '1867d645a675'


def upgrade():
    op.add_column('providers', sa.Column(
        'max_limit', sa.Integer(), default=0))


def downgrade():
    raise NotImplemented
