from alembic import op
import sqlalchemy as sa


"""add environment variables property for endpoint

Revision ID: 1f77126c0528
Revises: 3332aa012b73
Create Date: 2017-11-24 14:28:01.078402

"""

# revision identifiers, used by Alembic.
revision = '1f77126c0528'
down_revision = '3332aa012b73'


def upgrade():
    op.add_column(
        'endpoints', sa.Column('environment_variables', sa.JSON, default={})
    )


def downgrade():
    raise NotImplemented
