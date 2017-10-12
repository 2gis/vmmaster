from alembic import op
import sqlalchemy as sa

"""added endpoints statuses

Revision ID: 32b1bf95620a
Revises: cabd23253cb
Create Date: 2017-10-12 17:32:35.560057

"""

# revision identifiers, used by Alembic.
revision = '32b1bf95620a'
down_revision = 'cabd23253cb'


def upgrade():
    op.add_column('endpoints', sa.Column('mode', sa.String, default="default"))


def downgrade():
    raise NotImplemented
