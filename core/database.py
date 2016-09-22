# coding: utf-8

import asyncio
import logging
import sqlalchemy as sa
from core import utils
from aiopg.sa import create_engine
from backend.sessions import Session
from core.models import platforms_table, sessions_table


log = logging.getLogger(__name__)
metadata = sa.MetaData()


class Database(object):
    engine = None

    def __init__(self, app):
        self.app = app
        self.sessions_table = sessions_table
        self.platforms_table = platforms_table
        asyncio.wait(self.create_connection, loop=app.loop, timeout=60)

    async def create_connection(self):
        self.engine = await create_engine(
            dsn=self.app.cfg.DATABASE,
            loop=self.app.loop
        )

    async def get_session(self, session_id):
        async with self.engine:
            async with self.engine.acquire() as conn:
                query = (self.sessions_table.select().where(self.sessions_table.c.id == session_id))
                return await conn.execute(query)

    async def get_platform(self, name):
        async with self.engine:
            async with self.engine.acquire() as conn:
                query = (self.platforms_table.select().where(self.platforms_table.c.name == name))
                return await conn.execute(query)

    async def register_platforms(self, node, platforms):
        for name in platforms:
            await self.add(self.platforms_table, {"name": name, "node": node})

    async def unregister_platform(self, uuid):
        async with self.engine:
            async with self.engine.acquire() as conn:
                query = (self.platforms_table.delete().where(self.platforms_table.c.node == uuid))
                await conn.execute(query)

    async def add(self, table, values):
        if not self.engine:
            await self.create_connection()
        async with self.engine:
            async with self.engine.acquire() as conn:
                async with conn.begin():
                    await conn.execute(table.insert().values(**values))
