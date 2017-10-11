from alembic import op
import sqlalchemy as sa

"""New session status

Revision ID: 17dd20b2bdd8
Revises: 349c69643197
Create Date: 2017-09-02 12:53:55.980931

"""

# revision identifiers, used by Alembic.
revision = '17dd20b2bdd8'
down_revision = '349c69643197'


def upgrade():
    op.drop_constraint('status', 'sessions')
    op.alter_column(
        table_name='sessions', column_name='status',
        server_default='waiting',
        type_=sa.Enum(
            'unknown', 'running', 'succeed', 'failed', 'waiting', 'preparing', name='status', native_enum=False)
    )


def downgrade():
    op.drop_constraint('status', 'sessions')
    op.alter_column(
        table_name='sessions', column_name='status',
        type_=sa.Enum(
            'unknown', 'running', 'succeed', 'failed', 'waiting', name='status', native_enum=False)
    )
