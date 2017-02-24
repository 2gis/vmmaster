"""platforms

Revision ID: 2910519f8cbe
Revises: bff19a58f1f
Create Date: 2015-12-08 17:33:20.319225

"""

# revision identifiers, used by Alembic.
revision = '2910519f8cbe'
down_revision = 'bff19a58f1f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'platforms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('node', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('platforms')
