"""sessions and platforms

Revision ID: 1d74518ee142
Revises: 
Create Date: 2016-09-22 13:33:31.238779

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import Sequence, CreateSequence


# revision identifiers, used by Alembic.
revision = '1d74518ee142'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platforms',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String),
        sa.Column('node', sa.String)
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String),
        sa.Column('endpoint_id', sa.Integer),
        sa.Column('dc', sa.String),
        sa.Column('selenium_session', sa.String),
        sa.Column('take_screenshot', sa.Boolean),
        sa.Column('run_script', sa.String),
        sa.Column('created', sa.DateTime),
        sa.Column('modified', sa.DateTime),
        sa.Column('deleted', sa.DateTime),
        sa.Column('selenium_log', sa.String),

        # State
        sa.Column(
            'status',
            sa.Enum(
                'unknown', 'running', 'succeed', 'failed', 'waiting', name='status', native_enum=False
            ), default='waiting'),
        sa.Column('reason', sa.String),
        sa.Column('error', sa.String),
        sa.Column('timeouted', sa.Boolean, default=False),
        sa.Column('closed', sa.Boolean, default=False)
    )


def downgrade():
    op.drop_table('platforms')
    op.drop_table('sessions')

