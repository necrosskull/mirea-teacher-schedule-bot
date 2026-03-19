import os

import asyncio

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "data/bot.db")


async def migrate_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("PRAGMA table_info(schedulebot)")
        rows = await cursor.fetchall()
        existing_columns = {row[1] for row in rows}

        if "favorite" not in existing_columns:
            await conn.execute("ALTER TABLE schedulebot ADD COLUMN favorite TEXT")
            await conn.commit()


if __name__ == "__main__":
    asyncio.run(migrate_db())
