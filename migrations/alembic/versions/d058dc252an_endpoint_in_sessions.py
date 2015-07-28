"""sessions_in_db

Revision ID: d058dc252an
Revises: 4cb054526332
Create Date: 2015-07-10 16:12:46.794713

"""

revision = 'd058dc252an'
down_revision = '1d286235add5'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('sessions', sa.Column(
        'endpoint_id', sa.Integer(), nullable=True))
    op.add_column('sessions', sa.Column(
        'endpoint_ip', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column(
        'endpoint_name', sa.String(), nullable=True))
    op.drop_column('sessions', 'vm_id')

    op.add_column('virtual_machines', sa.Column(
        'time_deleted', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('sessions', 'endpoint_id')
    op.drop_column('sessions', 'endpoint_ip')
    op.drop_column('sessions', 'endpoint_name')
    op.add_column('sessions', sa.Column(
        'vm_id', sa.Integer(), nullable=True))

    op.drop_column('virtual_machines', 'time_deleted')