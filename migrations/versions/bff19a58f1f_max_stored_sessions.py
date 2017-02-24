"""max_stored_sessions

Revision ID: bff19a58f1f
Revises: 1de18183a7da
Create Date: 2015-11-16 16:03:44.999750

"""

# revision identifiers, used by Alembic.
revision = 'bff19a58f1f'
down_revision = '1de18183a7da'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('users', sa.Column(
        'max_stored_sessions', sa.Integer(), nullable=True)
    )
    op.execute(text(
        "UPDATE users "
        "SET max_stored_sessions = 200;")
    )


def downgrade():
    op.drop_column('users', 'max_stored_sessions')
