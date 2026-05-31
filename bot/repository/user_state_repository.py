from bot.db.sqlite import get_user_state, upsert_user_state


class UserStateRepository:
    async def save_payload(self, user_id: int, payload: str):
        await upsert_user_state(user_id, payload)

    async def load_payload(self, user_id: int) -> str | None:
        return await get_user_state(user_id)
