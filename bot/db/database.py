from aiogram.types import User

from bot.db.sqlite import NotificationUser, execute, fetchall, fetchone
from bot.fetch.models import SearchItem


async def insert_new_user(user: User):
    """
    Добавление нового пользователя в базу данных
    @param update: Обновление
    @param context: Контекст
    @return: None
    """
    try:
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
    except Exception:
        pass


async def add_favorite(user_id: int, favorite_text: str):
    try:
        await execute(
            "UPDATE schedulebot SET favorite = ? WHERE id = ?",
            (favorite_text, user_id),
        )
    except Exception:
        pass


async def get_user_favorites(user_id: int):
    try:
        row = await fetchone(
            "SELECT favorite FROM schedulebot WHERE id = ? AND favorite IS NOT NULL",
            (user_id,),
        )
        if row:
            return row["favorite"]

        return None
    except Exception:
        return None


async def set_notification(user_id: int, notify_time: str, item: SearchItem):
    try:
        await execute(
            """
            UPDATE schedulebot
            SET notify_enabled = 1,
                notify_time = ?,
                notify_type = ?,
                notify_uid = ?,
                notify_name = ?
            WHERE id = ?
            """,
            (notify_time, item.type, int(item.uid), item.name, user_id),
        )
    except Exception:
        pass


async def disable_notification(user_id: int):
    try:
        await execute(
            """
            UPDATE schedulebot
            SET notify_enabled = 0,
                notify_time = NULL,
                notify_type = NULL,
                notify_uid = NULL,
                notify_name = NULL
            WHERE id = ?
            """,
            (user_id,),
        )
    except Exception:
        pass


async def get_notification_users_by_time(notify_time: str):
    try:
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
    except Exception:
        return []


async def get_all_user_ids() -> list[int]:
    try:
        rows = await fetchall("SELECT id FROM schedulebot")
        return [row["id"] for row in rows]
    except Exception:
        return []


async def delete_user(user_id: int):
    try:
        await execute("DELETE FROM schedulebot WHERE id = ?", (user_id,))
    except Exception:
        pass
