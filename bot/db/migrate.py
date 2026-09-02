import asyncio
import os

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "data/bot.db")


async def migrate_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("PRAGMA table_info(schedulebot)")
        rows = await cursor.fetchall()
        existing_columns = {row[1] for row in rows}

        columns_to_add = {
            "favorite": "TEXT",
            "notify_enabled": "INTEGER DEFAULT 0",
            "notify_time": "TEXT",
            "notify_type": "TEXT",
            "notify_uid": "INTEGER",
            "notify_name": "TEXT",
            "last_notified_date": "TEXT",
            "created_at": "REAL DEFAULT 0",
            "last_active_at": "REAL DEFAULT 0",
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
            CREATE INDEX IF NOT EXISTS idx_schedulebot_activity
            ON schedulebot (last_active_at, created_at)
            """
        )


        await conn.commit()


if __name__ == "__main__":
    asyncio.run(migrate_db())
