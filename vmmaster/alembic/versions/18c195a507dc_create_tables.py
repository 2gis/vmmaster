"""create tables

Revision ID: 18c195a507dc
Revises: None
Create Date: 2015-02-25 15:00:45.604030

"""

# revision identifiers, used by Alembic.
revision = '18c195a507dc'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import Sequence, CreateSequence


def upgrade():
    # FIXME: sqlite not support sequence
    op.execute(CreateSequence(Sequence("log_step_id_seq")))
    op.execute(CreateSequence(Sequence("session_id_seq")))

    op.create_table(
        'log_steps',
        sa.Column('id', sa.Integer, sa.Sequence('log_step_id_seq'), primary_key=True),
        sa.Column('session_id', sa.Integer),
        sa.Column('control_line', sa.String),
        sa.Column('body', sa.String),
        sa.Column('screenshot', sa.String),
        sa.Column('time', sa.Float),
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer, sa.Sequence('session_id_seq'),  primary_key=True),
        sa.Column('name', sa.String),
        sa.Column('time', sa.Float),
    )


def downgrade():
    op.drop_table('log_steps')
    op.drop_table('sessions')