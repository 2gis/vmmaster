from alembic import op
import sqlalchemy as sa


"""Added vnc_proxy_port and vnc_proxy_pid

Revision ID: 2c579499c3aa
Revises: 2919ba26959e
Create Date: 2017-10-30 18:04:10.906886

"""

# revision identifiers, used by Alembic.
revision = '2c579499c3aa'
down_revision = '2919ba26959e'


def upgrade():
    op.add_column(
        'sessions', sa.Column('vnc_proxy_port', sa.Integer, default=None)
    )
    op.add_column(
        'sessions', sa.Column('vnc_proxy_pid', sa.Integer, default=None)
    )


def downgrade():
    raise NotImplemented
