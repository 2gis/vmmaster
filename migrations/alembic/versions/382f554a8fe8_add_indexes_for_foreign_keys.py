"""add indexes for foreign keys

Revision ID: 382f554a8fe8
Revises: f26e5c5e347
Create Date: 2015-03-24 11:27:22.240108

"""

revision = '382f554a8fe8'
down_revision = '4ec1ca506d1f'

from alembic import op


def upgrade():
    op.create_index('vmmaster_log_steps_fkey_idx', 'vmmaster_log_steps', ['session_id'])
    op.create_index('session_log_steps_fkey_idx', 'session_log_steps', ['vmmaster_log_step_id'])


def downgrade():
    op.drop_index('vmmaster_log_steps_fkey_idx')
    op.drop_index('session_log_steps_fkey_idx')
