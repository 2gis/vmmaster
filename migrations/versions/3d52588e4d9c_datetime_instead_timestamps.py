"""datetime_instead_timestamps

Revision ID: 3d52588e4d9c
Revises: 28049c768e17
Create Date: 2015-09-07 12:36:31.835220

"""

# revision identifiers, used by Alembic.
revision = '3d52588e4d9c'
down_revision = '28049c768e17'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    # Create default-named indexes
    op.create_index(
        op.f('ix_session_log_steps_session_id'),
        'session_log_steps',
        ['session_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_sub_steps_session_log_step_id'),
        'sub_steps',
        ['session_log_step_id'],
        unique=False
    )
    # Drop old-named indexes
    op.drop_index('session_log_steps_fkey_idx', table_name='session_log_steps')
    op.drop_index('sub_steps_fkey_idx', table_name='sub_steps')

    # Columns
    op.add_column(
        'session_log_steps', sa.Column('created', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'sessions', sa.Column('created', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'sessions', sa.Column('modified', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'sub_steps', sa.Column('created', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'virtual_machines', sa.Column('created', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'virtual_machines', sa.Column('done', sa.Boolean(), nullable=True)
    )
    op.execute(text(
        "UPDATE virtual_machines "
        "SET done = deleted;")
    )
    op.drop_column('virtual_machines', 'deleted')
    op.add_column(
        'virtual_machines', sa.Column('deleted', sa.DateTime(), nullable=True)
    )

    # Convert existing timestamps
    op.execute(text(
        "UPDATE sessions "
        "SET created = to_timestamp(time_created), "
        "modified = to_timestamp(time_modified);")
    )
    op.execute(text(
        "UPDATE session_log_steps "
        "SET created = to_timestamp(time_created);")
    )
    op.execute(text(
        "UPDATE sub_steps "
        "SET created = to_timestamp(time_created);")
    )
    op.execute(text(
        "UPDATE virtual_machines "
        "SET created = to_timestamp(time_created), "
        "deleted = to_timestamp(time_deleted);")
    )


def downgrade():
    # Drop new indexes
    op.drop_index(op.f('ix_sub_steps_session_log_step_id'),
                  table_name='sub_steps')
    op.drop_index(op.f('ix_session_log_steps_session_id'),
                  table_name='session_log_steps')

    # Restore old indexes
    op.create_index('sub_steps_fkey_idx', 'sub_steps', ['session_log_step_id'],
                    unique=False)
    op.create_index('session_log_steps_fkey_idx', 'session_log_steps',
                    ['session_id'], unique=False)

    # Drop new columns
    op.drop_column('virtual_machines', 'created')
    op.drop_column('sub_steps', 'created')
    op.drop_column('sessions', 'modified')
    op.drop_column('sessions', 'created')
    op.drop_column('session_log_steps', 'created')

    # Restore 'deleted'-column
    op.drop_column('virtual_machines', 'deleted')
    op.add_column('virtual_machines', sa.Column('deleted', sa.Boolean(),
                                                nullable=True))
    op.execute(text(
        "UPDATE virtual_machines "
        "SET deleted = done;")
    )
    op.drop_column('virtual_machines', 'done')
