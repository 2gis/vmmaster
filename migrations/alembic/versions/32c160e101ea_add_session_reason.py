"""add_session_reason

Revision ID: 32c160e101ea
Revises: 2910519f8cbe
Create Date: 2016-05-30 19:17:32.203167

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '32c160e101ea'
down_revision = '2910519f8cbe'


def upgrade():
    op.add_column('sessions', sa.Column('reason', sa.String(), nullable=True))


def downgrade():
    op.drop_column('sessions', 'reason')
