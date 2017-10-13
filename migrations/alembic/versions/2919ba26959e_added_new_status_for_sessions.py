from alembic import op
import sqlalchemy as sa


"""added new status for sessions

Revision ID: 2919ba26959e
Revises: 32b1bf95620a
Create Date: 2017-10-13 16:36:53.557683

"""

# revision identifiers, used by Alembic.
revision = '2919ba26959e'
down_revision = '32b1bf95620a'


def upgrade():
    op.alter_column(
        table_name='sessions', column_name='status',
        server_default='waiting',
        type_=sa.Enum(
            'unknown', 'running', 'succeed', 'failed', 'waiting', 'preparing', name='status', native_enum=False)
    )
    op.add_column(
        'sessions',
        sa.Column('screencast_started', sa.Boolean(), default=False)
    )


def downgrade():
    raise NotImplemented
