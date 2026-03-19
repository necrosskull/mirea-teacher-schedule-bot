from aiogram.types import User

from bot.repository import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def ensure_user(self, user: User):
        try:
            await self._user_repository.upsert_user(user)
        except Exception:
            pass

    async def set_favorite(self, user_id: int, favorite_text: str):
        try:
            await self._user_repository.set_favorite(user_id, favorite_text)
        except Exception:
            pass

    async def get_favorite(self, user_id: int) -> str | None:
        try:
            return await self._user_repository.get_favorite(user_id)
        except Exception:
            return None

    async def get_all_user_ids(self) -> list[int]:
        try:
            return await self._user_repository.get_all_user_ids()
        except Exception:
            return []

    async def count_all_users(self) -> int:
        try:
            return await self._user_repository.count_all_users()
        except Exception:
            return 0

    async def count_users_with_favorite(self) -> int:
        try:
            return await self._user_repository.count_users_with_favorite()
        except Exception:
            return 0

    async def count_users_with_notifications(self) -> int:
        try:
            return await self._user_repository.count_users_with_notifications()
        except Exception:
            return 0

    async def delete_user(self, user_id: int):
        try:
            await self._user_repository.delete_user(user_id)
        except Exception:
            pass
