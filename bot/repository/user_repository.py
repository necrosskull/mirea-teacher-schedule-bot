from aiogram.types import User

from bot.db.sqlite import NotificationUser, execute, fetchall, fetchone
from bot.fetch.models import SearchItem


class UserRepository:
    async def upsert_user(self, user: User):
        await execute(
            """
            INSERT INTO schedulebot (id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """,
            (user.id, user.username, user.first_name, user.last_name),
        )

    async def set_favorite(self, user_id: int, favorite_text: str):
        await execute(
            "UPDATE schedulebot SET favorite = ? WHERE id = ?",
            (favorite_text, user_id),
        )

    async def get_favorite(self, user_id: int) -> str | None:
        row = await fetchone(
            "SELECT favorite FROM schedulebot WHERE id = ? AND favorite IS NOT NULL",
            (user_id,),
        )
        if not row:
            return None

        return row["favorite"]

    async def set_notification(self, user_id: int, notify_time: str, item: SearchItem):
        await execute(
            """
            UPDATE schedulebot
            SET notify_enabled = 1,
                notify_time = ?,
                notify_type = ?,
                notify_uid = ?,
                notify_name = ?,
                last_notified_date = NULL
            WHERE id = ?
            """,
            (notify_time, item.type, int(item.uid), item.name, user_id),
        )

    async def disable_notification(self, user_id: int):
        await execute(
            """
            UPDATE schedulebot
            SET notify_enabled = 0,
                notify_time = NULL,
                notify_type = NULL,
                notify_uid = NULL,
                notify_name = NULL,
                last_notified_date = NULL
            WHERE id = ?
            """,
            (user_id,),
        )

    async def get_notification_users_by_time(
        self, notify_time: str
    ) -> list[NotificationUser]:
        rows = await fetchall(
            """
            SELECT id, notify_type, notify_uid, notify_name
            FROM schedulebot
            WHERE notify_enabled = 1
              AND notify_time = ?
              AND notify_type IS NOT NULL
              AND notify_uid IS NOT NULL
            """,
            (notify_time,),
        )
        return [
            NotificationUser(
                id=row["id"],
                notify_type=row["notify_type"],
                notify_uid=row["notify_uid"],
                notify_name=row["notify_name"],
            )
            for row in rows
        ]

    async def get_due_notification_users(
        self, current_time: str, delivery_date: str
    ) -> list[NotificationUser]:
        rows = await fetchall(
            """
            SELECT id, notify_type, notify_uid, notify_name
            FROM schedulebot
            WHERE notify_enabled = 1
              AND notify_time IS NOT NULL
              AND notify_time <= ?
              AND notify_type IS NOT NULL
              AND notify_uid IS NOT NULL
              AND (last_notified_date IS NULL OR last_notified_date < ?)
            ORDER BY notify_time, id
            """,
            (current_time, delivery_date),
        )
        return [
            NotificationUser(
                id=row["id"],
                notify_type=row["notify_type"],
                notify_uid=row["notify_uid"],
                notify_name=row["notify_name"],
            )
            for row in rows
        ]

    async def mark_notification_sent(self, user_id: int, delivery_date: str) -> bool:
        await execute(
            """
            UPDATE schedulebot
            SET last_notified_date = ?
            WHERE id = ?
            """,
            (delivery_date, user_id),
        )
        return True

    async def get_all_user_ids(self) -> list[int]:
        rows = await fetchall("SELECT id FROM schedulebot")
        return [row["id"] for row in rows]

    async def count_all_users(self) -> int:
        row = await fetchone("SELECT COUNT(*) AS cnt FROM schedulebot")
        if not row:
            return 0

        return int(row["cnt"])

    async def count_users_with_favorite(self) -> int:
        row = await fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM schedulebot
            WHERE favorite IS NOT NULL
              AND TRIM(favorite) != ''
            """
        )
        if not row:
            return 0

        return int(row["cnt"])

    async def count_users_with_notifications(self) -> int:
        row = await fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM schedulebot
            WHERE notify_enabled = 1
            """
        )
        if not row:
            return 0

        return int(row["cnt"])

    async def delete_user(self, user_id: int):
        await execute("DELETE FROM schedulebot WHERE id = ?", (user_id,))
