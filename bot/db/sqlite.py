import os
from dataclasses import dataclass

import aiosqlite

from bot.config import settings

DB_PATH = settings.db_path


def get_db_path() -> str:
    return settings.db_path


@dataclass
class NotificationUser:
    id: int
    notify_type: str
    notify_uid: int
    notify_name: str | None


async def init_db(db_path: str | None = None):
    path = db_path or get_db_path()
    db_dir = os.path.dirname(path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(path) as conn:

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
                notify_name TEXT,
                last_notified_date TEXT
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
            "last_notified_date": "TEXT",
        }

        for column, ddl in columns_to_add.items():
            if column not in existing_columns:
                await conn.execute(f"ALTER TABLE schedulebot ADD COLUMN {column} {ddl}")

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedulebot_notifications
            ON schedulebot (notify_enabled, notify_time, last_notified_date)
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schedule_cache_expires
            ON schedule_cache (expires_at)
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS item_requests (
                item_type TEXT NOT NULL,
                item_uid INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                request_count INTEGER DEFAULT 1,
                last_requested_at REAL NOT NULL,
                PRIMARY KEY (item_type, item_uid)
            )
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_item_requests_ranking
            ON item_requests (item_type, request_count DESC)
            """
        )

        await conn.commit()



async def fetchall(query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(query, params)
        return await cursor.fetchall()


async def fetchone(query: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with aiosqlite.connect(get_db_path()) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(query, params)
        return await cursor.fetchone()


async def execute(query: str, params: tuple = ()):
    async with aiosqlite.connect(get_db_path()) as conn:
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
