"""rename_agent_steps_to_substeps

Revision ID: 28049c768e17
Revises: 1441cc105fd9
Create Date: 2015-08-24 14:27:23.269437

"""

# revision identifiers, used by Alembic.
revision = '28049c768e17'
down_revision = '1441cc105fd9'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    # agent_log_steps -> sub_steps
    # Rename table
    op.rename_table('agent_log_steps', 'sub_steps')

    # Drop indexes
    op.drop_index('agent_log_steps_fkey_idx', 'sub_steps')

    # Drop constraints
    op.drop_constraint('agent_log_step_pkey', 'sub_steps')
    op.drop_constraint('agent_step_to_parent_fkey', 'sub_steps')

    # Rename sequence agent_log_steps_id_seq
    op.execute(text(
        "ALTER SEQUENCE agent_log_steps_id_seq "
        "RENAME TO sub_steps_id_seq"))

    op.create_primary_key("sub_step_pkey", "sub_steps", ["id"])

    # Add foreign key constraints
    op.create_foreign_key(name="sub_step_to_parent_fkey",
                          source="sub_steps",
                          referent="session_log_steps",
                          local_cols=["session_log_step_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')

    # Indexes
    op.create_index('sub_steps_fkey_idx',
                    'sub_steps',
                    ['session_log_step_id'])


def downgrade():
    # Drop new indexes
    op.drop_index('sub_steps_fkey_idx', 'sub_steps')

    # Drop new constraints
    op.drop_constraint('sub_step_pkey', 'sub_steps')
    op.drop_constraint('sub_step_to_parent_fkey', 'sub_steps')

    # Rename sequences back
    op.execute(text(
        "ALTER SEQUENCE sub_steps_id_seq "
        "RENAME TO agent_log_steps_id_seq"))

    # Rename tables back
    op.rename_table('sub_steps', 'agent_log_steps')

    # Pkey back
    op.create_primary_key("agent_log_step_pkey",
                          "agent_log_steps", ["id"])

    # Fkey back
    op.create_foreign_key(name="agent_step_to_parent_fkey",
                          source="agent_log_steps",
                          referent="session_log_steps",
                          local_cols=["session_log_step_id"],
                          remote_cols=["id"],
                          ondelete='CASCADE')

    # Indexes back
    op.create_index('agent_log_steps_fkey_idx', 'agent_log_steps',
                    ['vmmaster_log_step_id'])
