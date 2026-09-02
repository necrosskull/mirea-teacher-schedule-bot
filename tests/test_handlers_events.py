from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, User

from bot.config import settings
from bot.handlers.context import bot_data
from bot.handlers.events import (
    _extract_inline_link,
    _is_admin,
    send_message_to_all_users,
    stats,
    toggle_maintenance_mode,
)
from bot.service import UserService


def test_is_admin():
    settings.admins = [111, 222]

    msg_admin = AsyncMock(spec=Message)
    msg_admin.from_user = User(id=111, is_bot=False, first_name="Admin")
    assert _is_admin(msg_admin) is True

    msg_user = AsyncMock(spec=Message)
    msg_user.from_user = User(id=999, is_bot=False, first_name="User")
    assert _is_admin(msg_user) is False

    msg_none = AsyncMock(spec=Message)
    msg_none.from_user = None
    assert _is_admin(msg_none) is False


def test_extract_inline_link():
    text = "Important announcement [[Open site|https://example.com]]"
    cleaned, markup = _extract_inline_link(text)
    assert cleaned == "Important announcement"
    assert markup is not None
    assert markup.inline_keyboard[0][0].text == "Open site"
    assert markup.inline_keyboard[0][0].url == "https://example.com"

    # Plain text without link
    plain_text = "Just regular message"
    cleaned2, markup2 = _extract_inline_link(plain_text)
    assert cleaned2 == plain_text
    assert markup2 is None

    # Empty button text
    empty_btn = "Text [[|https://example.com]]"
    cleaned3, markup3 = _extract_inline_link(empty_btn)
    assert markup3 is None


@pytest.mark.asyncio
async def test_toggle_maintenance_mode():
    settings.admins = [100]
    bot_data["maintenance_mode"] = False
    bot_data["maintenance_message"] = None

    msg = AsyncMock(spec=Message)
    msg.from_user = User(id=100, is_bot=False, first_name="Admin")
    msg.text = "/work Технические работы"
    msg.answer = AsyncMock()

    # Toggle ON
    await toggle_maintenance_mode(msg)
    assert bot_data["maintenance_mode"] is True
    assert bot_data["maintenance_message"] == "Технические работы"
    assert "включен" in msg.answer.call_args[1]["text"]

    # Toggle OFF
    await toggle_maintenance_mode(msg)
    assert bot_data["maintenance_mode"] is False
    assert "отключен" in msg.answer.call_args[1]["text"]

    # Non-admin
    msg.from_user = User(id=999, is_bot=False, first_name="User")
    msg.answer.reset_mock()
    await toggle_maintenance_mode(msg)
    msg.answer.assert_not_called()


from tests.conftest import unwrap


@pytest.mark.asyncio
async def test_stats_handler(user_service: UserService):
    settings.admins = [100]

    # Non-admin
    msg_user = AsyncMock(spec=Message)
    msg_user.from_user = User(id=999, is_bot=False, first_name="User")
    msg_user.answer = AsyncMock()
    await unwrap(stats)(msg_user, user_service)
    msg_user.answer.assert_not_called()

    # Record some item requests
    await user_service.record_item_request("teacher", 1, "Афанасьев М.С.")
    await user_service.record_item_request("teacher", 1, "Афанасьев М.С.")
    await user_service.record_item_request("group", 10, "КТСО-01-22")
    await user_service.record_item_request("classroom", 100, "ИВЦ-101 (В-78)")

    # Admin
    msg_admin = AsyncMock(spec=Message)
    msg_admin.from_user = User(id=100, is_bot=False, first_name="Admin")
    msg_admin.answer = AsyncMock()
    await unwrap(stats)(msg_admin, user_service)
    msg_admin.answer.assert_called_once()
    text = msg_admin.answer.call_args[0][0]
    assert "Статистика бота" in text
    assert "Топ-3 преподавателей" in text
    assert "Афанасьев М.С. — 2 зап." in text
    assert "КТСО-01-22 — 1 зап." in text
    assert "ИВЦ-101 (В-78) — 1 зап." in text



@pytest.mark.asyncio
async def test_send_message_to_all_users_flow(user_service: UserService):
    settings.admins = [100]
    await user_service.ensure_user(User(id=201, is_bot=False, first_name="U1"))
    await user_service.ensure_user(User(id=202, is_bot=False, first_name="U2"))
    await user_service.ensure_user(User(id=203, is_bot=False, first_name="U3"))

    msg = AsyncMock(spec=Message)
    msg.from_user = User(id=100, is_bot=False, first_name="Admin")
    msg.text = "/send Привет всем!"
    msg.bot = AsyncMock()

    # User 201 succeeds, 202 has forbidden error (blocked), 203 has temporary error
    async def mock_send(chat_id, **kwargs):
        if chat_id == 202:
            raise TelegramForbiddenError(method="sendMessage", message="Bot was blocked by the user")
        if chat_id == 203:
            raise ConnectionError("Network timeout")
        return AsyncMock()

    msg.bot.send_message = AsyncMock(side_effect=mock_send)

    with patch("asyncio.sleep", AsyncMock()):
        await unwrap(send_message_to_all_users)(msg, user_service)

    remaining_ids = await user_service.get_all_user_ids()
    # 201 (success) remains
    assert 201 in remaining_ids
    # 202 (blocked) was deleted
    assert 202 not in remaining_ids
    # 203 (temporary network error) was NOT deleted!
    assert 203 in remaining_ids

