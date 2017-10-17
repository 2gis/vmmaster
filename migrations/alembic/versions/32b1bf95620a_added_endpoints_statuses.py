from alembic import op
import sqlalchemy as sa

"""added endpoints statuses

Revision ID: 32b1bf95620a
Revises: 8b323312e72
Create Date: 2017-10-12 17:32:35.560057

"""

# revision identifiers, used by Alembic.
revision = '32b1bf95620a'
down_revision = '8b323312e72'


def upgrade():
    op.add_column('endpoints', sa.Column('mode', sa.String, default="default"))


def downgrade():
    raise NotImplemented
