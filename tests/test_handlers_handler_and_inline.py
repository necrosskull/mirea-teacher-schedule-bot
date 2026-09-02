import datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ChosenInlineResult, InlineQuery, Message, User

from bot.fetch.models import (
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
from bot.handlers.context import bot_data, get_user_data, set_state_service
from bot.handlers.handler import (
    _session_key_from_callback,
    callback_dispatcher,
    deny_old_message,
    favourite,
    get_query_handler,
    got_day_handler,
    got_item_clarification_handler,
    got_week_handler,
    maintenance_message,
    message_dispatcher,
)
from bot.handlers.inline import (
    answer_inline_handler,
    deny_inline_usage,
    handle_inline_query,
    handle_query,
    inline_dispatcher,
)
import bot.handlers.states as st
from bot.service import ScheduleService, StateService, UserService
from tests.conftest import unwrap



@pytest.mark.asyncio
async def test_session_key_from_callback():
    cb_msg = AsyncMock(spec=CallbackQuery)
    cb_msg.message = AsyncMock()
    cb_msg.message.message_id = 1234
    cb_msg.inline_message_id = None
    assert _session_key_from_callback(cb_msg) == "1234"

    cb_inline = AsyncMock(spec=CallbackQuery)
    cb_inline.message = None
    cb_inline.inline_message_id = "inline_99"
    assert _session_key_from_callback(cb_inline) == "inline_99"

    cb_none = AsyncMock(spec=CallbackQuery)
    cb_none.message = None
    cb_none.inline_message_id = None
    assert _session_key_from_callback(cb_none) is None


@pytest.mark.asyncio
async def test_get_query_handler_short_query(user_service: UserService, schedule_service: ScheduleService, sample_user: User):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "ab"
    msg.via_bot = False
    msg.answer = AsyncMock()

    await get_query_handler(msg, user_service, schedule_service)
    msg.answer.assert_called_once()
    assert "Слишком короткий запрос" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_get_query_handler_aud_query(user_service: UserService, schedule_service: ScheduleService, sample_user: User):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "аудитория 101"
    msg.via_bot = False
    msg.answer = AsyncMock()

    await get_query_handler(msg, user_service, schedule_service)
    msg.answer.assert_called_once()
    assert "Для поиска по аудиториям" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_get_query_handler_single_result(
    user_service: UserService,
    schedule_service: ScheduleService,
    mock_api_client,
    sample_user: User,
):
    item = SearchItem(type="teacher", uid=10, name="Карпов")
    mock_api_client.search.return_value = [item]
    mock_api_client.get_schedule.return_value = ScheduleData(data=[])

    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "Карпов"
    msg.via_bot = False
    msg.chat = AsyncMock()
    msg.chat.id = 12345
    msg.bot = AsyncMock()
    msg.bot.send_message.return_value = AsyncMock(message_id=555)

    target = await get_query_handler(msg, user_service, schedule_service)
    assert target == st.GETWEEK


@pytest.mark.asyncio
async def test_get_query_handler_multiple_results(
    user_service: UserService,
    schedule_service: ScheduleService,
    mock_api_client,
    sample_user: User,
):
    items = [
        SearchItem(type="teacher", uid=10, name="Иванов И.И."),
        SearchItem(type="teacher", uid=11, name="Иванов П.П."),
    ]
    mock_api_client.search.return_value = items

    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "Иванов"
    msg.via_bot = False
    msg.chat = AsyncMock()
    msg.chat.id = 12345
    msg.bot = AsyncMock()
    msg.bot.send_message.return_value = AsyncMock(message_id=666)

    target = await get_query_handler(msg, user_service, schedule_service)
    assert target == st.ITEM_CLARIFY


@pytest.mark.asyncio
async def test_got_week_handler_navigation():
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock(message_id=100)
    cb.inline_message_id = None
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()

    user_data = {
        "message_ids": [100],
        "available_items": None,
        "item": SearchItem(type="teacher", uid=1, name="T"),
        "schedule": ScheduleData(data=[]),
    }

    # Digits -> chooses week
    cb.data = "5"
    target = await got_week_handler(cb, user_data)
    assert target == st.GETDAY
    assert user_data["week"] == 5

    # Today
    cb.data = "today"
    target_today = await got_week_handler(cb, user_data)
    assert user_data["date"] == datetime.date.today()
    assert user_data["week"] is None

    # Tomorrow
    cb.data = "tomorrow"
    target_tomorrow = await got_week_handler(cb, user_data)
    assert user_data["date"] == datetime.date.today() + datetime.timedelta(days=1)


@pytest.mark.asyncio
async def test_got_day_handler_chill_and_back():
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock(message_id=100)
    cb.inline_message_id = None
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()

    user_data = {
        "message_ids": [100],
        "week": 1,
        "item": SearchItem(type="teacher", uid=1, name="T"),
        "schedule": ScheduleData(data=[]),
    }

    # Chill button
    cb.data = "chill"
    target_chill = await got_day_handler(cb, user_data)
    assert target_chill == st.GETDAY
    assert "В этот день пар нет" in cb.answer.call_args[1]["text"]

    # Back button
    cb.data = "back"
    target_back = await got_day_handler(cb, user_data)
    assert target_back == st.GETWEEK


@pytest.mark.asyncio
async def test_fav_command(user_service: UserService, schedule_service: ScheduleService, sample_user: User):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.answer = AsyncMock()

    # Without saved favorite
    await unwrap(favourite)(msg, user_service, schedule_service)
    assert "нет сохраненного расписания" in msg.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_inline_handlers(user_service: UserService, schedule_service: ScheduleService, mock_api_client, sample_user: User):
    # handle_inline_query with favorite
    await user_service.ensure_user(sample_user)
    await user_service.set_favorite(sample_user.id, "ИКБО-20-23")

    mock_api_client.search.return_value = [
        SearchItem(type="group", uid=202, name="ИКБО-20-23")
    ]

    iq = AsyncMock(spec=InlineQuery)
    iq.id = "q1"
    iq.from_user = sample_user
    iq.query = ""
    iq.answer = AsyncMock()

    await unwrap(handle_inline_query)(iq, user_service, schedule_service)
    iq.answer.assert_called_once()
    results = iq.answer.call_args[0][0]
    assert len(results) == 1
    assert results[0].title == "ИКБО-20-23"


@pytest.mark.asyncio
async def test_chosen_inline_result_and_dispatcher(schedule_service: ScheduleService, sample_user: User):
    cir = AsyncMock(spec=ChosenInlineResult)
    cir.from_user = sample_user
    cir.result_id = "teacher:10:Карпов"
    cir.inline_message_id = "inline_msg_777"

    await unwrap(answer_inline_handler)(cir, AsyncMock())

    pdata = await get_user_data(sample_user.id)
    assert "inline_sessions" in pdata
    assert "inline_msg_777" in pdata["inline_sessions"]

    # Test inline_dispatcher callback
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = sample_user
    cb.inline_message_id = "inline_msg_777"
    cb.data = "5"
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()

    with patch("bot.handlers.handler.got_week_handler", AsyncMock(return_value=st.GETDAY)):
        await unwrap(inline_dispatcher)(cb, schedule_service)

    # Deny inline usage if unknown inline_message_id
    cb.inline_message_id = "unknown_id"
    await unwrap(inline_dispatcher)(cb, schedule_service)
    assert "Вы не можете использовать это меню" in cb.answer.call_args[1]["text"]


@pytest.mark.asyncio
async def test_deny_old_message():
    # Test for regular message
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock(message_id=50)
    cb.inline_message_id = None
    cb.answer = AsyncMock()

    # Allowed when message_id in message_ids
    assert await deny_old_message(cb, {"message_ids": [50]}) is False

    # Denied when message_id not in message_ids
    assert await deny_old_message(cb, {"message_ids": [99]}) is True
    assert "не относится к вашему текущему запросу" in cb.answer.call_args[1]["text"]

    # Test for inline message
    cb_inline = AsyncMock(spec=CallbackQuery)
    cb_inline.message = None
    cb_inline.inline_message_id = "inl_50"
    cb_inline.answer = AsyncMock()

    assert await deny_old_message(cb_inline, {"inline_message_ids": ["inl_50"]}) is False
    assert await deny_old_message(cb_inline, {"inline_message_ids": ["inl_99"]}) is True


@pytest.mark.asyncio
async def test_got_item_clarification_handler(schedule_service: ScheduleService, mock_api_client):
    item1 = SearchItem(type="teacher", uid=10, name="Иванов И.И.")
    item2 = SearchItem(type="teacher", uid=20, name="Иванов П.П.")

    mock_api_client.get_schedule.return_value = ScheduleData(data=[])

    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock(message_id=10)
    cb.inline_message_id = None
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()

    user_data = {
        "message_ids": [10],
        "available_items": [item1, item2],
    }

    # Selecting valid item
    cb.data = "teacher:10"
    with patch("bot.handlers.send.send_week_selector", AsyncMock(return_value=st.GETWEEK)):
        target = await got_item_clarification_handler(cb, user_data, schedule_service)
        assert target == st.GETWEEK
        assert user_data["item"] == item1

    # Selecting item not in available_items
    cb.data = "teacher:99"
    target_invalid = await got_item_clarification_handler(cb, user_data, schedule_service)
    assert target_invalid is None
    assert "Ошибка, сделайте новый запрос" in cb.answer.call_args[1]["text"]

    # Back button
    cb.data = "back"
    with patch("bot.handlers.send.resend_name_input", AsyncMock(return_value="back_target")):
        target_back = await got_item_clarification_handler(cb, user_data, schedule_service)
        assert target_back == "back_target"


@pytest.mark.asyncio
async def test_callback_dispatcher_flow(schedule_service: ScheduleService, sample_user: User):
    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = sample_user
    cb.message = AsyncMock(message_id=100)
    cb.inline_message_id = None
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = "5"

    pdata = await get_user_data(sample_user.id)

    # Unknown session -> denies
    await unwrap(callback_dispatcher)(cb, schedule_service)
    assert "не относится к вашему текущему запросу" in cb.answer.call_args[1]["text"]

    # Valid session with step GETWEEK
    pdata["sessions"] = {
        "100": {
            "message_ids": [100],
            "item": SearchItem(type="teacher", uid=1, name="T"),
            "schedule": None,
            "step": st.GETWEEK,
        }
    }

    with patch("bot.handlers.handler.got_week_handler", AsyncMock(return_value=st.GETDAY)):
        await unwrap(callback_dispatcher)(cb, schedule_service)
        assert pdata["sessions"]["100"]["step"] == st.GETDAY


@pytest.mark.asyncio
async def test_message_dispatcher(user_service: UserService, schedule_service: ScheduleService, sample_user: User):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "query"
    msg.via_bot = False

    with patch("bot.handlers.handler.get_query_handler", AsyncMock()) as mock_gqh:
        await unwrap(message_dispatcher)(msg, user_service, schedule_service)
        mock_gqh.assert_called_once_with(msg, user_service=user_service, schedule_service=schedule_service)


