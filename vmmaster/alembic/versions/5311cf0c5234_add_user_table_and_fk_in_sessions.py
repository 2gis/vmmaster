"""Add user table and fk in sessions

Revision ID: 5311cf0c5234
Revises: 382f554a8fe8
Create Date: 2015-03-31 12:26:26.377220

"""

# revision identifiers, used by Alembic.
revision = '5311cf0c5234'
down_revision = '382f554a8fe8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.create_table(
        'user_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hash', sa.String(length=160), nullable=True),
        sa.Column('salt', sa.String(length=16), nullable=True),
        sa.Column('group_id', sa.Integer(), default=0, nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['user_groups.id'], ondelete='SET DEFAULT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('salt'),
        sa.UniqueConstraint('username')
    )
    op.add_column('sessions', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('sessions_fkey_idx', 'sessions', ['user_id'])
    # Seed data:
    op.get_bind().execute(text("insert into user_groups (id, name) values (0, 'NOGROUP')"))
    op.get_bind().execute(text("insert into users (id, group_id, username) values (0, 0, 'anonymous')"))


def downgrade():
    op.drop_column('sessions', 'user_id')
    op.drop_table('users')
    op.drop_table('user_groups')
