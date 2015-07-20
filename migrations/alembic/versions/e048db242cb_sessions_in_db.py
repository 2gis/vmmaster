"""sessions_in_db

Revision ID: e048db242cb
Revises: 4cb054526332
Create Date: 2015-07-10 16:12:46.794713

"""

revision = 'e048db242cb'
down_revision = '4cb054526332'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.execute(text(
        "ALTER TABLE agent_log_steps "
        "RENAME COLUMN time TO time_created"))

    op.execute(text(
        "ALTER TABLE session_log_steps "
        "RENAME COLUMN time TO time_created"))

    op.execute(text(
        "ALTER TABLE sessions "
        "RENAME COLUMN time TO time_created"))

    op.execute(text(
        "ALTER TABLE virtual_machines "
        "RENAME COLUMN created TO time_created"))

    op.add_column('sessions', sa.Column(
        'closed', sa.Boolean(), nullable=True))
    op.add_column('sessions', sa.Column(
        'desired_capabilities', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column(
        'platform', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column(
        'timeouted', sa.Boolean(), nullable=True))
    op.add_column('sessions', sa.Column(
        'time_modified', sa.Float(), nullable=True))
    op.add_column('sessions', sa.Column(
        'selenium_session', sa.String(), nullable=True))

    op.execute(text(
        "UPDATE sessions "
        "SET time_modified = time_created"
    ))

    op.drop_constraint("status", "sessions")

    op.alter_column(
        'sessions', 'status',
        sa.Enum('unknown', 'running', 'succeed', 'failed', 'waiting',
                name='status', native_enum=False))

    op.drop_column('users', 'salt')


def downgrade():
    op.drop_column('sessions', 'selenium_session')
    op.drop_column('sessions', 'time_modified')
    op.drop_column('sessions', 'timeouted')
    op.drop_column('sessions', 'platform')
    op.drop_column('sessions', 'desired_capabilities')
    op.drop_column('sessions', 'closed')

    op.execute(text(
        "ALTER TABLE agent_log_steps "
        "RENAME COLUMN time_created TO time"))

    op.execute(text(
        "ALTER TABLE session_log_steps "
        "RENAME COLUMN time_created TO time"))

    op.execute(text(
        "ALTER TABLE sessions "
        "RENAME COLUMN time_created TO time"))

    op.execute(text(
        "ALTER TABLE virtual_machines "
        "RENAME COLUMN time_created TO created"))
