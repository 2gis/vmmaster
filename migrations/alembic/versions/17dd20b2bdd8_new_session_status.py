from alembic import op
import sqlalchemy as sa

"""New session status

Revision ID: 17dd20b2bdd8
Revises: 175aecf5691f
Create Date: 2017-09-02 12:53:55.980931

"""

# revision identifiers, used by Alembic.
revision = '17dd20b2bdd8'
down_revision = '175aecf5691f'


def upgrade():
    op.drop_column('sessions', 'status')
    op.add_column(
        'sessions',
        sa.Column('status', sa.Enum(
            'unknown',
            'running',
            'succeed',
            'failed',
            'waiting',
            'preparing',
            name='status',
            native_enum=False
        ), default='waiting')
    )


def downgrade():
    op.drop_column('sessions', 'status')
    op.add_column(
        'sessions',
        sa.Column('status', sa.Enum(
            'unknown',
            'running',
            'succeed',
            'failed',
            'waiting',
            name='status',
            native_enum=False
        ), default='waiting')
    )
