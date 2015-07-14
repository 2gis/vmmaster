"""add foreign keys

Revision ID: 4ec1ca506d1f
Revises: f26e5c5e347
Create Date: 2015-03-19 11:34:16.695193

"""

# revision identifiers, used by Alembic.
revision = '4ec1ca506d1f'
down_revision = '1eb29cd1981'

from alembic import op


def upgrade():
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


def downgrade():
    op.drop_constraint(name="fk_vmmaster_log_step_to_session",
                       table_name="vmmaster_log_steps",
                       type_="foreignkey")
    op.drop_constraint(name="fk_session_log_step_to_vmmaster_log_step",
                       table_name="session_log_steps",
                       type_="foreignkey")
