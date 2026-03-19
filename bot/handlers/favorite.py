from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka, inject

from bot.handlers.states import FavoriteStates
from bot.service import UserService

router = Router()


@router.message(Command("save"))
@inject
async def save_favourite(
    message: Message,
    state: FSMContext,
    user_service: FromDishka[UserService],
):
    """
    Привествие бота при использовании команды /start
    """
    await user_service.ensure_user(message.from_user)
    await state.set_state(FavoriteStates.awaiting_favorite)

    await message.answer(
        text="ℹ️ Введите запрос для сохранения в избранное\n\nПример: `ИКБО-20-23`",
    )


@router.message(
    StateFilter(FavoriteStates.awaiting_favorite), F.text & ~F.text.startswith("/")
)
@inject
async def ask_favourite(
    message: Message,
    state: FSMContext,
    user_service: FromDishka[UserService],
):
    await user_service.set_favorite(message.from_user.id, message.text)
    await state.clear()

    query = await user_service.get_favorite(message.from_user.id)
    await message.answer(
        text=f"✅ Успешно добавлено: {query}\n\nЧтобы посмотреть сохраненное расписание, используйте команду /fav",
    )


def init_handlers(dispatcher):
    dispatcher.include_router(router)
