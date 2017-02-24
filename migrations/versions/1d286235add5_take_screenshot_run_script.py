"""take_screenshot_run_script

Revision ID: 1d286235add5
Revises: e048db242cb
Create Date: 2015-07-31 14:42:05.939137

"""

# revision identifiers, used by Alembic.
revision = '1d286235add5'
down_revision = 'e048db242cb'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('sessions', sa.Column('run_script', sa.String(),
                                        nullable=True))
    op.add_column('sessions', sa.Column('take_screenshot', sa.Boolean(),
                                        nullable=True))
    op.execute(text(
        "ALTER TABLE sessions "
        "RENAME COLUMN desired_capabilities TO dc"))


def downgrade():
    op.execute(text(
        "ALTER TABLE sessions "
        "RENAME COLUMN dc TO desired_capabilities"))

    op.drop_column('sessions', 'take_screenshot')
    op.drop_column('sessions', 'run_script')
