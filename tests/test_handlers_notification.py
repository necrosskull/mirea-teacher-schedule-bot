import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from bot.db.sqlite import NotificationUser
from bot.fetch.models import (
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
from bot.handlers.notification import (
    _extract_item,
    _get_current_msk_time,
    _process_notification_user,
    _send_blocks,
    notification_worker,
    notify_item_pick,
    notify_item_text_fallback,
    notify_off,
    notify_query_input,
    notify_set_time,
    notify_start,
)
from bot.handlers.states import NotificationStates
from bot.service import NotificationService, ScheduleService, UserService
from tests.conftest import unwrap


def test_extract_item():
    item = SearchItem(type="teacher", uid=1, name="T")
    assert _extract_item(item) == item
    assert _extract_item({"type": "group", "uid": 2, "name": "G"}).uid == 2
    assert _extract_item("invalid") is None
    assert _extract_item({"invalid": "dict"}) is None


@pytest.mark.asyncio
async def test_send_blocks():
    bot = AsyncMock()

    # Empty blocks
    await _send_blocks(bot, 123, "Header", [])
    bot.send_message.assert_called_once_with(chat_id=123, text="Header")

    bot.reset_mock()
    # Normal blocks fitting into one message
    await _send_blocks(bot, 123, "Header", ["Block 1\n", "Block 2\n"])
    assert bot.send_message.call_count == 1
    sent_text = bot.send_message.call_args[1]["text"]
    assert "Header\n\nBlock 1\nBlock 2\n" == sent_text

    bot.reset_mock()
    # Large blocks causing split
    large_block = "A" * 4000
    await _send_blocks(bot, 123, "Header", [large_block, "B" * 500])
    assert bot.send_message.call_count == 2


def test_get_current_msk_time():
    now = _get_current_msk_time()
    assert isinstance(now, datetime.datetime)
    assert now.tzinfo is not None


@pytest.mark.asyncio
async def test_notify_start_with_direct_query(
    mock_fsm_context: FSMContext,
    user_service: UserService,
    schedule_service: ScheduleService,
    sample_user: User,
    mock_api_client,
):
    mock_api_client.search.return_value = [SearchItem(type="teacher", uid=1, name="Карпов")]

    msg = AsyncMock(spec=Message)

    msg.from_user = sample_user
    msg.text = "/notify Карпов"
    msg.answer = AsyncMock()

    await unwrap(notify_start)(msg, mock_fsm_context, user_service, schedule_service)
    state = await mock_fsm_context.get_state()
    assert state == NotificationStates.awaiting_time.state


@pytest.mark.asyncio
async def test_notify_start_without_query(
    mock_fsm_context: FSMContext,
    user_service: UserService,
    schedule_service: ScheduleService,
    sample_user: User,
):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "/notify"
    msg.answer = AsyncMock()

    await unwrap(notify_start)(msg, mock_fsm_context, user_service, schedule_service)
    state = await mock_fsm_context.get_state()
    assert state == NotificationStates.awaiting_query.state


@pytest.mark.asyncio
async def test_notify_query_input_multiple_items(
    mock_fsm_context: FSMContext,
    schedule_service: ScheduleService,
    sample_user: User,
    mock_api_client,
):
    mock_api_client.search.return_value = [
        SearchItem(type="teacher", uid=1, name="T1"),
        SearchItem(type="teacher", uid=2, name="T2"),
    ]

    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.text = "T"
    msg.answer = AsyncMock()

    await unwrap(notify_query_input)(msg, mock_fsm_context, schedule_service)
    state = await mock_fsm_context.get_state()
    assert state == NotificationStates.awaiting_item.state


@pytest.mark.asyncio
async def test_notify_item_pick(mock_fsm_context: FSMContext):
    await mock_fsm_context.update_data(
        notify_items=[
            {"type": "teacher", "uid": 1, "name": "T1"},
            {"type": "teacher", "uid": 2, "name": "T2"},
        ]
    )

    cb = AsyncMock(spec=CallbackQuery)
    cb.data = "teacher:2"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()

    await notify_item_pick(cb, mock_fsm_context)
    state = await mock_fsm_context.get_state()
    assert state == NotificationStates.awaiting_time.state


@pytest.mark.asyncio
async def test_notify_set_time(
    mock_fsm_context: FSMContext,
    notification_service: NotificationService,
    sample_user: User,
):
    item = SearchItem(type="teacher", uid=1, name="Карпов")
    await mock_fsm_context.update_data(notify_item=item.model_dump())

    # Invalid time
    msg_bad = AsyncMock(spec=Message)
    msg_bad.from_user = sample_user
    msg_bad.text = "25:70"
    msg_bad.answer = AsyncMock()

    await unwrap(notify_set_time)(msg_bad, mock_fsm_context, notification_service)
    assert "Неверный формат" in msg_bad.answer.call_args[0][0]

    # Valid time
    msg_ok = AsyncMock(spec=Message)
    msg_ok.from_user = sample_user
    msg_ok.text = "08:15"
    msg_ok.answer = AsyncMock()

    await unwrap(notify_set_time)(msg_ok, mock_fsm_context, notification_service)
    assert "Рассылка на завтра включена" in msg_ok.answer.call_args[0][0]
    assert await mock_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_notify_off(
    mock_fsm_context: FSMContext,
    notification_service: NotificationService,
    sample_user: User,
):
    msg = AsyncMock(spec=Message)
    msg.from_user = sample_user
    msg.answer = AsyncMock()

    await unwrap(notify_off)(msg, mock_fsm_context, notification_service)
    msg.answer.assert_called_once_with("✅ Рассылка отключена.")



@pytest.mark.asyncio
async def test_process_notification_user_with_lessons(
    notification_service: NotificationService,
    mock_api_client,
    schedule_service: ScheduleService,
    mock_bot,
):
    user = NotificationUser(id=500, notify_type="teacher", notify_uid=1, notify_name="Преподаватель")
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).date()

    lesson = LessonSchedule(
        dates=[tomorrow.strftime("%d-%m-%Y")],
        lesson_bells=LessonBells(number=1, start_time="09:00", end_time="10:30"),
        subject="Физика",
    )
    mock_api_client.get_schedule.return_value = ScheduleData(data=[lesson])

    semaphore = asyncio.Semaphore(1)
    await _process_notification_user(
        user,
        bot=mock_bot,
        notification_service=notification_service,
        schedule_service=schedule_service,
        delivery_date=datetime.date.today().isoformat(),
        now=datetime.datetime.now(),
        semaphore=semaphore,
    )
    assert mock_bot.send_message.called


@pytest.mark.asyncio
async def test_process_notification_user_blocked(
    notification_service: NotificationService,
    mock_api_client,
    schedule_service: ScheduleService,
    mock_bot,
):
    user = NotificationUser(id=501, notify_type="teacher", notify_uid=1, notify_name="T")
    mock_api_client.get_schedule.return_value = ScheduleData(data=[])
    mock_bot.send_message.side_effect = TelegramForbiddenError(
        method="sendMessage", message="Bot blocked by user"
    )

    semaphore = asyncio.Semaphore(1)
    await _process_notification_user(
        user,
        bot=mock_bot,
        notification_service=notification_service,
        schedule_service=schedule_service,
        delivery_date="2025-09-01",
        now=datetime.datetime.now(),
        semaphore=semaphore,
    )
    # Should disable notifications for user
    due = await notification_service.get_due_notification_users("23:59", "2025-09-02")
    assert 501 not in [u.id for u in due]


@pytest.mark.asyncio
async def test_notification_worker_loop(
    notification_service: NotificationService,
    schedule_service: ScheduleService,
    mock_bot,
):
    with patch("bot.handlers.notification.NOTIFY_POLL_INTERVAL_SECONDS", 0.01):
        task = asyncio.create_task(
            notification_worker(mock_bot, notification_service, schedule_service)
        )
        await asyncio.sleep(0.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

