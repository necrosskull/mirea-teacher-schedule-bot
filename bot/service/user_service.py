from aiogram.types import User

from bot.logs.lazy_logger import lazy_logger
from bot.repository import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def ensure_user(self, user: User):
        try:
            await self._user_repository.upsert_user(user)
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.ensure_user failed: {e}")

    async def set_favorite(self, user_id: int, favorite_text: str):
        try:
            await self._user_repository.set_favorite(user_id, favorite_text)
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.set_favorite failed for user={user_id}: {e}")

    async def get_favorite(self, user_id: int) -> str | None:
        try:
            return await self._user_repository.get_favorite(user_id)
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.get_favorite failed for user={user_id}: {e}")
            return None

    async def get_all_user_ids(self) -> list[int]:
        try:
            return await self._user_repository.get_all_user_ids()
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.get_all_user_ids failed: {e}")
            return []

    async def count_all_users(self) -> int:
        try:
            return await self._user_repository.count_all_users()
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.count_all_users failed: {e}")
            return 0

    async def count_users_with_favorite(self) -> int:
        try:
            return await self._user_repository.count_users_with_favorite()
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.count_users_with_favorite failed: {e}")
            return 0

    async def count_users_with_notifications(self) -> int:
        try:
            return await self._user_repository.count_users_with_notifications()
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.count_users_with_notifications failed: {e}")
            return 0

    async def delete_user(self, user_id: int):
        try:
            await self._user_repository.delete_user(user_id)
        except Exception as e:
            lazy_logger.logger.exception(f"UserService.delete_user failed for user={user_id}: {e}")

    async def record_item_request(self, item_type: str, item_uid: int, item_name: str):
        try:
            await self._user_repository.record_item_request(item_type, item_uid, item_name)
        except Exception as e:
            lazy_logger.logger.warning(f"UserService.record_item_request failed: {e}")

    async def get_top_requested_items(
        self, item_type: str, limit: int = 3
    ) -> list[tuple[str, int]]:
        try:
            return await self._user_repository.get_top_requested_items(item_type, limit)
        except Exception as e:
            lazy_logger.logger.warning(f"UserService.get_top_requested_items failed: {e}")
            return []
