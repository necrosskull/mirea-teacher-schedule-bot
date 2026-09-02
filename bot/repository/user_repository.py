import time

from aiogram.types import User

from bot.db.sqlite import NotificationUser, execute, fetchall, fetchone

from bot.fetch.models import SearchItem


class UserRepository:
    async def upsert_user(self, user: User):
        now = time.time()
        await execute(
            """
            INSERT INTO schedulebot (id, username, first_name, last_name, created_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_active_at = excluded.last_active_at,
                created_at = CASE WHEN schedulebot.created_at IS NULL OR schedulebot.created_at = 0 THEN excluded.created_at ELSE schedulebot.created_at END
            """,
            (user.id, user.username, user.first_name, user.last_name, now, now),
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

    async def record_item_request(
        self, item_type: str, item_uid: int, item_name: str
    ):
        now = time.time()
        await execute(
            """
            INSERT INTO item_requests (item_type, item_uid, item_name, request_count, last_requested_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(item_type, item_uid) DO UPDATE SET
                request_count = request_count + 1,
                item_name = excluded.item_name,
                last_requested_at = excluded.last_requested_at
            """,
            (item_type, item_uid, item_name, now),
        )

    async def get_top_requested_items(
        self, item_type: str, limit: int = 3
    ) -> list[tuple[str, int]]:
        rows = await fetchall(
            """
            SELECT item_name, request_count
            FROM item_requests
            WHERE item_type = ?
            ORDER BY request_count DESC, last_requested_at DESC
            LIMIT ?
            """,
            (item_type, limit),
        )
        return [(str(row[0]), int(row[1])) for row in rows]

    async def record_user_activity(

        self, user_id: int, first_name: str | None = None, username: str | None = None
    ):
        now = time.time()
        await execute(
            """
            INSERT INTO schedulebot (id, username, first_name, created_at, last_active_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_active_at = excluded.last_active_at,
                username = COALESCE(excluded.username, schedulebot.username),
                first_name = COALESCE(excluded.first_name, schedulebot.first_name),
                created_at = CASE WHEN schedulebot.created_at IS NULL OR schedulebot.created_at = 0 THEN excluded.created_at ELSE schedulebot.created_at END
            """,
            (user_id, username, first_name, now, now),
        )

    async def get_active_users_count(self, seconds: int) -> int:
        threshold = time.time() - seconds
        row = await fetchone(
            "SELECT COUNT(*) FROM schedulebot WHERE last_active_at >= ?",
            (threshold,),
        )
        return int(row[0]) if row else 0

    async def get_new_users_count(self, seconds: int) -> int:
        threshold = time.time() - seconds
        row = await fetchone(
            "SELECT COUNT(*) FROM schedulebot WHERE created_at >= ?",
            (threshold,),
        )
        return int(row[0]) if row else 0

    async def get_requests_distribution(self) -> dict[str, int]:
        rows = await fetchall(
            "SELECT item_type, SUM(request_count) FROM item_requests GROUP BY item_type"
        )
        res = {"group": 0, "teacher": 0, "classroom": 0}
        for r in rows:
            if r[0] in res:
                res[r[0]] = int(r[1] or 0)
        return res

    async def get_total_requests_count(self) -> int:
        row = await fetchone("SELECT SUM(request_count) FROM item_requests")
        return int(row[0] or 0) if row and row[0] is not None else 0

    async def get_top_notification_times(self, limit: int = 5) -> list[tuple[str, int]]:
        rows = await fetchall(
            """
            SELECT notify_time, COUNT(*) as cnt
            FROM schedulebot
            WHERE notify_enabled = 1 AND notify_time IS NOT NULL
            GROUP BY notify_time
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(str(r[0]), int(r[1])) for r in rows] if rows else []


