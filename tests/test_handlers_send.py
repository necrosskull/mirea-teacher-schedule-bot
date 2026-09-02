import datetime
from unittest.mock import AsyncMock, MagicMock, patch


import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from bot.fetch.models import (
    Campus,
    Classroom,
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
import bot.handlers.send as send
import bot.handlers.states as st


def test_register_message_id():
    user_data = {}
    send._register_message_id(user_data, 100)
    assert user_data["message_id"] == 100
    assert user_data["message_ids"] == [100]

    # Add up to 35 message IDs -> capped at 30
    for i in range(101, 140):
        send._register_message_id(user_data, i)
    assert len(user_data["message_ids"]) == 30
    assert user_data["message_id"] == 139


@pytest.mark.asyncio
async def test_edit_callback_message():
    # With inline_message_id
    cb_inline = AsyncMock(spec=CallbackQuery)
    cb_inline.inline_message_id = "inline_123"
    cb_inline.message = None
    cb_inline.bot = AsyncMock()

    await send._edit_callback_message(cb_inline, "Text 1")
    cb_inline.bot.edit_message_text.assert_called_once_with(
        text="Text 1", inline_message_id="inline_123", reply_markup=None
    )

    # With regular message
    cb_msg = AsyncMock(spec=CallbackQuery)
    cb_msg.inline_message_id = None
    cb_msg.message = AsyncMock()

    await send._edit_callback_message(cb_msg, "Text 2")
    cb_msg.message.edit_text.assert_called_once_with(text="Text 2", reply_markup=None)


@pytest.mark.asyncio
async def test_send_item_clarity():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=AsyncMock(message_id=50))

    items = [SearchItem(type="teacher", uid=1, name="T")]
    user_data = {"available_items": items}

    # firsttime with chat_id is None -> returns st.ITEM_CLARIFY
    target_none = await send.send_item_clarity(AsyncMock(), bot, user_data, firsttime=True, chat_id=None)
    assert target_none == st.ITEM_CLARIFY

    # firsttime with chat_id
    target_first = await send.send_item_clarity(AsyncMock(), bot, user_data, firsttime=True, chat_id=123)
    assert target_first == st.ITEM_CLARIFY
    assert user_data["message_id"] == 50

    # not firsttime -> edits callback message
    cb = AsyncMock(spec=CallbackQuery)
    cb.inline_message_id = None
    cb.message = AsyncMock()
    target_second = await send.send_item_clarity(cb, bot, user_data, firsttime=False)
    assert target_second == st.ITEM_CLARIFY
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_send_week_selector():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=AsyncMock(message_id=60))

    for item_type in ["teacher", "classroom", "group"]:
        user_data = {"item": SearchItem(type=item_type, uid=1, name="ItemName")}
        # firsttime=True
        target = await send.send_week_selector(AsyncMock(), bot, user_data, firsttime=True, chat_id=123)
        assert target == st.GETWEEK

        # not firsttime
        cb = AsyncMock(spec=CallbackQuery)
        cb.inline_message_id = None
        cb.message = AsyncMock()
        await send.send_week_selector(cb, bot, user_data, firsttime=False)
        cb.message.edit_text.assert_called()


@pytest.mark.asyncio
async def test_send_day_selector():
    cb = AsyncMock(spec=CallbackQuery)
    cb.inline_message_id = None
    cb.message = AsyncMock()

    user_data = {
        "item": SearchItem(type="teacher", uid=1, name="Карпов"),
        "week": 3,
        "schedule": ScheduleData(data=[]),
    }

    target = await send.send_day_selector(cb, user_data)
    assert target == st.GETDAY
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_send_result_and_delivery_optimisation():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=AsyncMock(message_id=70))

    lesson = LessonSchedule(
        dates=["01-09-2025"],
        lesson_bells=LessonBells(number=1, start_time="09:00", end_time="10:30"),
        subject="Линал",
    )
    schedule = ScheduleData(data=[lesson])

    cb = AsyncMock(spec=CallbackQuery)
    cb.inline_message_id = None
    cb.message = AsyncMock(chat=AsyncMock(id=12345))
    cb.answer = AsyncMock()
    cb.bot = bot

    user_data = {
        "item": SearchItem(type="teacher", uid=1, name="Карпов"),
        "schedule": schedule,
        "date": datetime.date(2025, 9, 1),
        "week": None,
    }

    with patch("bot.handlers.send.get_dates_for_week", return_value=[datetime.date(2025, 9, 1)]):
        target = await send.send_result(cb, bot, user_data, show_week=False)
        assert target == st.GETDAY
        cb.message.edit_text.assert_called_once()

        # Show week
        cb.message.edit_text.reset_mock()
        target_week = await send.send_result(cb, bot, user_data, show_week=True)
        assert target_week == st.GETDAY


@pytest.mark.asyncio
async def test_delivery_optimisation_multi_chunk():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=AsyncMock(message_id=80))

    cb = AsyncMock(spec=CallbackQuery)
    cb.inline_message_id = None
    cb.message = AsyncMock(chat=AsyncMock(id=123))
    cb.answer = AsyncMock()
    cb.bot = bot

    user_data = {
        "item": SearchItem(type="teacher", uid=1, name="T"),
        "schedule": ScheduleData(data=[]),
        "date": datetime.date(2025, 9, 1),
        "week": 1,
    }

    # 3 large blocks exceeding 4096 bytes
    b1 = "A" * 3000
    b2 = "B" * 3000
    b3 = "C" * 1000

    target = await send.telegram_delivery_optimisation(cb, bot, user_data, [b1, b2, b3])
    assert target == st.GETDAY
    cb.message.edit_text.assert_called()
    assert bot.send_message.called


@pytest.mark.asyncio
async def test_delivery_optimisation_inline_overflow():
    bot = AsyncMock(spec=Bot)

    cb = AsyncMock(spec=CallbackQuery)
    cb.inline_message_id = "inline_999"
    cb.message = None
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()

    user_data = {
        "item": SearchItem(type="teacher", uid=1, name="T"),
        "schedule": ScheduleData(data=[]),
        "week": 1,
    }

    # Oversized blocks in inline mode
    b1 = "A" * 4000
    b2 = "B" * 500

    target = await send.telegram_delivery_optimisation(cb, bot, user_data, [b1, b2])
    cb.answer.assert_called_once()
    assert "Слишком длинное расписание" in cb.answer.call_args[1]["text"]



@pytest.mark.asyncio
async def test_resend_name_input():
    cb = AsyncMock(spec=CallbackQuery)
    cb.answer = AsyncMock()
    await send.resend_name_input(cb)
    cb.answer.assert_called_once()
    assert "Введите новый запрос" in cb.answer.call_args[1]["text"]
