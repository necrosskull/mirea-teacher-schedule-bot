from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User

from bot.handlers.favorite import ask_favourite, save_favourite
from bot.handlers.states import FavoriteStates
from bot.service import UserService
from tests.conftest import unwrap


@pytest.mark.asyncio
async def test_save_favourite(user_service: UserService, mock_fsm_context: FSMContext, sample_user: User):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.answer = AsyncMock()

    await unwrap(save_favourite)(msg, mock_fsm_context, user_service)

    state = await mock_fsm_context.get_state()
    assert state == FavoriteStates.awaiting_favorite.state
    msg.answer.assert_called_once()
    assert "ИКБО-20-23" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_ask_favourite(user_service: UserService, mock_fsm_context: FSMContext, sample_user: User):
    await mock_fsm_context.set_state(FavoriteStates.awaiting_favorite)

    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "ИКБО-20-23"
    msg.answer = AsyncMock()

    await unwrap(ask_favourite)(msg, mock_fsm_context, user_service)

    state = await mock_fsm_context.get_state()
    assert state is None  # State cleared

    saved = await user_service.get_favorite(sample_user.id)
    assert saved == "ИКБО-20-23"
    msg.answer.assert_called_once()
    assert "Успешно добавлено: ИКБО-20-23" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_favourite_none_user(user_service: UserService, mock_fsm_context: FSMContext):
    msg = AsyncMock(spec=Message)
    msg.from_user = None

    await unwrap(save_favourite)(msg, mock_fsm_context, user_service)
    await unwrap(ask_favourite)(msg, mock_fsm_context, user_service)
    assert await mock_fsm_context.get_state() is None
