# coding: utf-8

from alembic import op
import sqlalchemy as sa

"""
Add session column take_screencast
Revision ID: cabd23253cb
Revises: 349c69643197
Create Date: 2017-10-10 16:14:31.157887

"""

# revision identifiers, used by Alembic.
revision = 'cabd23253cb'
down_revision = '349c69643197'


def upgrade():
    op.add_column('sessions', sa.Column('take_screencast', sa.Boolean(), nullable=True))


def downgrade():
    raise NotImplemented
