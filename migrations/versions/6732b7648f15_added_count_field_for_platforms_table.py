"""added count field for platforms table

Revision ID: 6732b7648f15
Revises: 1d74518ee142
Create Date: 2016-10-21 18:01:34.475563

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6732b7648f15'
down_revision = '1d74518ee142'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('platforms', sa.Column('count', sa.Integer, default=0))


def downgrade():
    op.drop_column('platforms', 'count')
