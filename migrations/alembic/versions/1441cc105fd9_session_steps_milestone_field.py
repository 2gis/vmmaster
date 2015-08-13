"""session_steps_milestone_field

Revision ID: 1441cc105fd9
Revises: 1d286235add5
Create Date: 2015-08-12 12:02:02.087501

"""

# revision identifiers, used by Alembic.
revision = '1441cc105fd9'
down_revision = 'd058dc252an'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.add_column('session_log_steps', sa.Column('milestone', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('session_log_steps', 'milestone')
