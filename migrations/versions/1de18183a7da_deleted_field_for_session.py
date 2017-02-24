"""deleted_field_for_session

Revision ID: 1de18183a7da
Revises: 3d52588e4d9c
Create Date: 2015-10-07 18:20:57.252212

"""

# revision identifiers, used by Alembic.
revision = '1de18183a7da'
down_revision = '3d52588e4d9c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('sessions', sa.Column('deleted', sa.DateTime(),
                                        nullable=True))


def downgrade():
    op.drop_column('sessions', 'deleted')
