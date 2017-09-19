from alembic import op
import sqlalchemy as sa

"""endpoints_table
Revision ID: 175aecf5691f
Revises: 250c6848576f
Create Date: 2017-08-21 15:11:34.888686
"""

# revision identifiers, used by Alembic.
revision = '175aecf5691f'
down_revision = '250c6848576f'


def upgrade():
    op.drop_column('sessions', 'endpoint_ip')
    op.drop_column('sessions', 'endpoint_name')

    op.create_table(
        'providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.drop_column('platforms', 'node')
    op.add_column('platforms', sa.Column('provider_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_platforms_provider',
        'platforms', 'providers',
        ['provider_id'], ['id'],
    )

    op.create_table(
        'endpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform_id', sa.Integer()),
        sa.Column('provider_id', sa.Integer()),
        sa.Column('uuid', sa.String()),
        sa.Column('name', sa.String()),
        sa.Column('ip', sa.String()),
        sa.Column('ports', sa.JSON()),
        sa.Column('platform_name', sa.String()),
        sa.Column('ready', sa.Boolean()),
        sa.Column('in_use', sa.Boolean(), default=False),
        sa.Column('deleted', sa.Boolean()),
        sa.Column('created_time', sa.DateTime(), default=None),
        sa.Column('used_time', sa.DateTime(), default=None),
        sa.Column('deleted_time', sa.DateTime(), default=None),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    )

    op.create_foreign_key(
        'fk_sessions_endpoint',
        'sessions', 'endpoints',
        ['endpoint_id'], ['id'],
    )


def downgrade():
    op.drop_constraint('fk_sessions_endpoint', 'sessions')
    op.drop_table('endpoints')
    op.add_column('sessions', sa.Column('endpoint_ip', sa.Float()))
    op.add_column('sessions', sa.Column('endpoint_name', sa.Float()))

    op.add_column('platforms', sa.Column('node', sa.String(length=100), nullable=True))
    op.drop_constraint('fk_platforms_provider', 'platforms')
    op.drop_table('providers')
    op.drop_column('platforms', 'provider_id')
