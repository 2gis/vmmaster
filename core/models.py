# coding: utf-8

from datetime import datetime
import sqlalchemy as sa


metadata = sa.MetaData()

sessions_table = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String),
    sa.Column("endpoint_id", sa.Integer),
    sa.Column("dc", sa.String),
    sa.Column("selenium_session", sa.String),
    sa.Column("take_screenshot", sa.Boolean),
    sa.Column("run_script", sa.String),
    sa.Column("created", sa.DateTime, default=datetime.now),
    sa.Column("modified", sa.DateTime, default=datetime.now),
    sa.Column("deleted", sa.DateTime),
    sa.Column("selenium_log", sa.String),

    # State
    sa.Column("status",
              sa.Enum(
                  'unknown', 'running', 'succeed', 'failed', 'waiting', name='status', native_enum=False
              ), default='waiting'),
    sa.Column("reason", sa.String),
    sa.Column("error", sa.String),
    sa.Column("timeouted", sa.Boolean, default=False),
    sa.Column("closed", sa.Boolean, default=False)
)

platforms_table = sa.Table(
    "platforms",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("node", sa.String(length=100), nullable=False),
    sa.Column("name", sa.String(length=100), nullable=False),
    sa.Column("count", sa.Integer(), default=0)
)
