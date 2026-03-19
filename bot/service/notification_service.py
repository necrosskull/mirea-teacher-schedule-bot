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

    async def get_notification_users_by_time(self, notify_time: str) -> list[NotificationUser]:
        try:
            return await self._user_repository.get_notification_users_by_time(notify_time)
        except Exception:
            return []
