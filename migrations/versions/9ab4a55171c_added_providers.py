"""added providers

Revision ID: 9ab4a55171c
Revises: 575ac791bca9
Create Date: 2017-03-09 16:30:26.493615

"""

# revision identifiers, used by Alembic.
revision = '9ab4a55171c'
down_revision = '575ac791bca9'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('providers',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(), nullable=True),
                    sa.Column('url', sa.String(), nullable=True),
                    sa.Column('active', sa.Boolean(), nullable=True),
                    sa.PrimaryKeyConstraint('id'))
    op.drop_column('platforms', 'node')
    op.add_column('platforms', sa.Column('provider_id', sa.Integer(), nullable=True))
    op.add_column('endpoints', sa.Column('platform_id', sa.Integer(), nullable=True))
    op.add_column('endpoints', sa.Column('provider_id', sa.Integer(), nullable=True))
    op.add_column('endpoints', sa.Column('in_use', sa.Boolean(), default=False))
    op.create_foreign_key(
        'fk_platforms_provider',
        'platforms', 'providers',
        ['provider_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_endpoints_provider',
        'endpoints', 'providers',
        ['provider_id'], ['id'],
    )


def downgrade():
    op.add_column('platforms', sa.Column('node', sa.String(length=100), nullable=True))
    op.drop_constraint('fk_platforms_provider', 'platforms')
    op.drop_constraint('fk_endpoints_provider', 'endpoints')
    op.drop_table('providers')
    op.drop_column('platforms', 'provider_id')
    op.drop_column('endpoints', 'provider_id')
    op.drop_column('endpoints', 'platform_id')
    op.drop_column('endpoints', 'in_use')
