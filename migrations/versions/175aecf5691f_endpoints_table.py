"""endpoints_table

Revision ID: 175aecf5691f
Revises: 4f80a6b3ffc2
Create Date: 2017-02-21 15:11:34.888686

"""

# revision identifiers, used by Alembic.
revision = '175aecf5691f'
down_revision = '4f80a6b3ffc2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('virtual_machines')
    op.drop_column('sessions', 'endpoint_ip')
    op.drop_column('sessions', 'endpoint_name')
    op.create_table('endpoints',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(), nullable=True),
                    sa.Column('ip', sa.String(), nullable=True),
                    sa.Column('mac', sa.String(), nullable=True),
                    sa.Column('platform', sa.String(), nullable=True),
                    sa.Column('ready', sa.Boolean(), nullable=True),
                    sa.Column('checking', sa.Boolean(), nullable=True),
                    sa.Column('deleted', sa.Boolean, nullable=True),
                    sa.Column('created', sa.Float, nullable=True),
                    sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('endpoints')
