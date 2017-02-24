"""Rename tables

Revision ID: 4cb054526332
Revises: 37f924a78337
Create Date: 2015-07-10 12:27:11.600414

"""

revision = '4cb054526332'
down_revision = '37f924a78337'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    # session_log_steps -> agent_log_steps
    # Rename table
    op.rename_table('session_log_steps', 'agent_log_steps')

    # Drop indexes
    op.drop_index('session_log_steps_fkey_idx', 'agent_log_steps')

    # Drop constraints
    op.drop_constraint('session_log_steps_pkey', 'agent_log_steps')
    op.drop_constraint('fk_session_log_step_to_vmmaster_log_step',
                       'agent_log_steps')

    # Rename foreign key column
    op.execute(text(
        "ALTER TABLE agent_log_steps "
        "RENAME COLUMN vmmaster_log_step_id TO session_log_step_id"))

    # Rename sequence session_log_steps_id_seq
    op.execute(text(
        "ALTER SEQUENCE session_log_steps_id_seq "
        "RENAME TO agent_log_steps_id_seq"))

    # vmmaster_log_steps -> session_log_steps
    # Rename table
    op.rename_table('vmmaster_log_steps', 'session_log_steps')

    # Drop indexes
    op.drop_index('vmmaster_log_steps_fkey_idx', 'session_log_steps')

    # Drop constraints
    op.drop_constraint('log_steps_pkey', 'session_log_steps')
    op.drop_constraint('fk_vmmaster_log_step_to_session', 'session_log_steps')

    # Rename sequence vmmaster_log_steps_id_seq
    op.execute(text(
        "ALTER SEQUENCE vmmaster_log_steps_id_seq "
        "RENAME TO session_log_steps_id_seq"))

    # Add primary key constraints
    op.create_primary_key("session_log_step_pkey", "session_log_steps", ["id"])
    op.create_primary_key("agent_log_step_pkey", "agent_log_steps", ["id"])

    # Add foreign key constraints
    op.create_foreign_key(name="agent_step_to_parent_fkey",
                          source="agent_log_steps",
                          referent="session_log_steps",
                          local_cols=["session_log_step_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')
    op.create_foreign_key(name="session_step_to_parent_fkey",
                          source="session_log_steps",
                          referent="sessions",
                          local_cols=["session_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')

    # Indexes
    op.create_index('agent_log_steps_fkey_idx',
                    'agent_log_steps',
                    ['session_log_step_id'])
    op.create_index('session_log_steps_fkey_idx',
                    'session_log_steps',
                    ['session_id'])


def downgrade():
    # Drop new indexes
    op.drop_index('agent_log_steps_fkey_idx', 'agent_log_steps')
    op.drop_index('session_log_steps_fkey_idx', 'session_log_steps')

    # Drop new constraints
    op.drop_constraint('agent_log_step_pkey', 'agent_log_steps')
    op.drop_constraint('agent_step_to_parent_fkey', 'agent_log_steps')
    op.drop_constraint('session_log_step_pkey', 'session_log_steps')
    op.drop_constraint('session_step_to_parent_fkey', 'session_log_steps')

    # Rename sequences back
    op.execute(text(
        "ALTER SEQUENCE session_log_steps_id_seq "
        "RENAME TO vmmaster_log_steps_id_seq"))
    op.execute(text(
        "ALTER SEQUENCE agent_log_steps_id_seq "
        "RENAME TO session_log_steps_id_seq"))

    # Rename foreign key column back
    op.execute(text(
        "ALTER TABLE agent_log_steps "
        "RENAME COLUMN session_log_step_id TO vmmaster_log_step_id"))

    # Rename tables back
    op.rename_table('session_log_steps', 'vmmaster_log_steps')
    op.rename_table('agent_log_steps', 'session_log_steps')

    # Pkey back
    op.create_primary_key("log_steps_pkey", "vmmaster_log_steps", ["id"])
    op.create_primary_key("session_log_steps_pkey",
                          "session_log_steps", ["id"])

    # Fkey back
    op.create_foreign_key(name="fk_vmmaster_log_step_to_session",
                          source="vmmaster_log_steps",
                          referent="sessions",
                          local_cols=["session_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')
    op.create_foreign_key(name="fk_session_log_step_to_vmmaster_log_step",
                          source="session_log_steps",
                          referent="vmmaster_log_steps",
                          local_cols=["vmmaster_log_step_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')

    # Indexes back
    op.create_index('vmmaster_log_steps_fkey_idx', 'vmmaster_log_steps',
                    ['session_id'])
    op.create_index('session_log_steps_fkey_idx', 'session_log_steps',
                    ['vmmaster_log_step_id'])
