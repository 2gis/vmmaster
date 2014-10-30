"""add session log table

Revision ID: 1eb29cd1981
Revises: 19c195a507dc
Create Date: 2014-10-30 11:52:00.073153

"""

# revision identifiers, used by Alembic.
revision = '1eb29cd1981'
down_revision = '19c195a507dc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.rename_table('log_steps', 'vmmaster_log_steps')
    op.create_table(
        'session_log_steps',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('vmmaster_log_step_id', sa.Integer),
        sa.Column('control_line', sa.String),
        sa.Column('body', sa.String),
        sa.Column('time', sa.Float)
    )


def downgrade():
    op.rename_table('vmmaster_log_steps', 'log_steps')
    op.drop_table('session_log_steps')
