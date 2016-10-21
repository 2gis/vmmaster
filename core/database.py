# coding: utf-8

import asyncio
import logging
import sqlalchemy as sa
from aiopg.sa import create_engine
from core.models import platforms_table, sessions_table


log = logging.getLogger(__name__)
metadata = sa.MetaData()


class Database(object):
    def __init__(self, app):
        self.app = app
        self.sessions_table = sessions_table
        self.platforms_table = platforms_table
        asyncio.wait(self.create_connection, loop=app.loop, timeout=60)

    async def create_connection(self):
        return await create_engine(
            dsn=self.app.cfg.DATABASE,
            loop=self.app.loop
        )

    async def get_session(self, session_id):
        engine = await self.create_connection()
        async with engine:
            async with engine.acquire() as conn:
                query = (self.sessions_table.select().where(self.sessions_table.c.id == "%s" % session_id))
                return await conn.execute(query)

    async def get_platform(self, name):
        engine = await self.create_connection()
        async with engine:
            async with engine.acquire() as conn:
                query = (self.platforms_table.select().where(self.platforms_table.c.name == "%s" % name))
                return await conn.execute(query)

    async def get_platforms(self, uuid):
        platforms = {}
        engine = await self.create_connection()
        async with engine:
            async with engine.acquire() as conn:
                query = (self.platforms_table.select().where(self.platforms_table.c.node == "%s" % uuid))
                async for row in conn.execute(query):
                    platforms[row.name] = row.count
                return platforms

    async def register_platforms(self, node, platforms):
        log.info("Registering platforms: %s" % platforms)
        for name, count in platforms.items():
            log.info("Platform %s was registered with count %s" % (name, count))
            await self.add(self.platforms_table, {"name": name, "node": node, "count": count})

    async def unregister_platform(self, uuid):
        engine = await self.create_connection()
        async with engine:
            async with engine.acquire() as conn:
                query = (self.platforms_table.delete().where(self.platforms_table.c.node == "%s" % uuid))
                await conn.execute(query)

    async def add(self, table, values):
        engine = await self.create_connection()
        async with engine:
            async with engine.acquire() as conn:
                async with conn.begin():
                    await conn.execute(table.insert().values(**values))
