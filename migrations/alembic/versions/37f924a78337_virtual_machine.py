"""virtual_machine
Revision ID: 37f924a78337
Revises: bea3ba88c73
Create Date: 2015-06-24 17:26:36.552058
"""

# revision identifiers, used by Alembic.
revision = '37f924a78337'
down_revision = 'bea3ba88c73'

from alembic import op
import sqlalchemy as sa
# from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table('virtual_machines',
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

    op.add_column('sessions', sa.Column('vm_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('sessions', 'vm_id')
    op.drop_table('virtual_machines')