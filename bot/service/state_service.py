from bot.repository import UserStateRepository


class StateService:
    def __init__(self, user_state_repository: UserStateRepository):
        self._user_state_repository = user_state_repository

    async def save_payload(self, user_id: int, payload: str):
        await self._user_state_repository.save_payload(user_id, payload)

    async def load_payload(self, user_id: int) -> str | None:
        return await self._user_state_repository.load_payload(user_id)
