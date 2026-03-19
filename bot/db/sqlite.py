import os
from dataclasses import dataclass

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "data/bot.db")


@dataclass
class NotificationUser:
    id: int
    notify_type: str
    notify_uid: int
    notify_name: str | None


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedulebot (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                favorite TEXT,
                notify_enabled INTEGER DEFAULT 0,
                notify_time TEXT,
                notify_type TEXT,
                notify_uid INTEGER,
                notify_name TEXT
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS userstate (
                user_id INTEGER PRIMARY KEY,
                payload TEXT DEFAULT '{}'
            )
            """
        )

        cursor = await conn.execute("PRAGMA table_info(schedulebot)")
        rows = await cursor.fetchall()
        existing_columns = {row[1] for row in rows}

        columns_to_add = {
            "notify_enabled": "INTEGER DEFAULT 0",
            "notify_time": "TEXT",
            "notify_type": "TEXT",
            "notify_uid": "INTEGER",
            "notify_name": "TEXT",
        }

        for column, ddl in columns_to_add.items():
            if column not in existing_columns:
                await conn.execute(f"ALTER TABLE schedulebot ADD COLUMN {column} {ddl}")

        await conn.commit()


async def fetchall(query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(query, params)
        return await cursor.fetchall()


async def fetchone(query: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(query, params)
        return await cursor.fetchone()


async def execute(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(query, params)
        await conn.commit()


async def upsert_user_state(user_id: int, payload: str):
    await execute(
        """
        INSERT INTO userstate (user_id, payload)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET payload = excluded.payload
        """,
        (user_id, payload),
    )


async def get_user_state(user_id: int) -> str | None:
    row = await fetchone("SELECT payload FROM userstate WHERE user_id = ?", (user_id,))
    if not row:
        return None

    return row["payload"]
