from alembic import op
import sqlalchemy as sa


"""Add config column to providers

Revision ID: 349c69643197
Revises: 175aecf5691f
Create Date: 2017-09-22 12:52:21.660885

"""

# revision identifiers, used by Alembic.
revision = '349c69643197'
down_revision = '175aecf5691f'


def upgrade():
    op.add_column(
        'providers',
        sa.Column('config', sa.JSON(), nullable=True)
    )


def downgrade():
    raise NotImplemented
