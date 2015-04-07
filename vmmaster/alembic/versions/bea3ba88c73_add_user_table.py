"""add user table

Revision ID: bea3ba88c73
Revises: 382f554a8fe8
Create Date: 2015-04-07 13:45:22.348137

"""

# revision identifiers, used by Alembic.
revision = 'bea3ba88c73'
down_revision = '382f554a8fe8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=30), nullable=False),
        sa.Column('password', sa.String(length=128), nullable=True),
        sa.Column('salt', sa.String(length=16), nullable=True),
        sa.Column('allowed_machines', sa.Integer(), nullable=True),
        sa.Column('is_staff', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('date_joined', sa.DateTime(), nullable=True),
        sa.Column('token', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('salt'),
        sa.UniqueConstraint('username')
    )
    op.add_column('sessions', sa.Column('user_id', sa.Integer(), nullable=True))
    # Create default user
    op.get_bind().execute(text("INSERT INTO users (id, is_active, username) VALUES (0, True, 'anonymous')"))


def downgrade():
    op.drop_column('sessions', 'user_id')
    op.drop_table('users')

