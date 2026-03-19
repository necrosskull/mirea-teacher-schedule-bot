from bot.db.sqlite import NotificationUser
from bot.fetch.models import SearchItem
from bot.repository import UserRepository


class NotificationService:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def set_notification(self, user_id: int, notify_time: str, item: SearchItem):
        try:
            await self._user_repository.set_notification(user_id, notify_time, item)
        except Exception:
            pass

    async def disable_notification(self, user_id: int):
        try:
            await self._user_repository.disable_notification(user_id)
        except Exception:
            pass

    async def get_due_notification_users(
        self, current_time: str, delivery_date: str
    ) -> list[NotificationUser]:
        try:
            return await self._user_repository.get_due_notification_users(
                current_time, delivery_date
            )
        except Exception:
            return []

    async def mark_notification_sent(self, user_id: int, delivery_date: str) -> bool:
        try:
            return await self._user_repository.mark_notification_sent(
                user_id, delivery_date
            )
        except Exception:
            return False
