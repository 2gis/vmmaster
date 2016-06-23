"""created selenium_log field for session

Revision ID: 4f80a6b3ffc2
Revises: 32c160e101ea
Create Date: 2016-06-22 18:20:31.957015

"""

# revision identifiers, used by Alembic.
revision = '4f80a6b3ffc2'
down_revision = '32c160e101ea'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('sessions', sa.Column('selenium_log', sa.String))


def downgrade():
    op.drop_column('sessions', 'selenium_log')
