import asyncio
import datetime
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka, inject

import bot.handlers.construct as construct
from bot.fetch.models import SearchItem
from bot.handlers.states import NotificationStates
from bot.logs.lazy_logger import lazy_logger
from bot.parse.formating import format_outputs
from bot.service import NotificationService, ScheduleService, UserService

router = Router()

TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
NOTIFY_CONCURRENCY = 10
NOTIFY_POLL_INTERVAL_SECONDS = 10


def _extract_item(raw_item):
    if isinstance(raw_item, SearchItem):
        return raw_item

    if isinstance(raw_item, dict):
        try:
            return SearchItem(**raw_item)
        except Exception:
            return None

    return None


async def _send_blocks(bot, chat_id: int, header: str, blocks: list[str]):
    if not blocks:
        await bot.send_message(chat_id=chat_id, text=header)
        return

    chunk = header + "\n\n"
    for block in blocks:
        if len(chunk) + len(block) <= 4096:
            chunk += block
        else:
            await bot.send_message(chat_id=chat_id, text=chunk)
            chunk = block

    if chunk:
        await bot.send_message(chat_id=chat_id, text=chunk)


def _get_current_msk_time() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(hours=3)


async def _mark_notification_sent(
    notification_service: NotificationService, user_id: int, delivery_date: str
):
    marked = await notification_service.mark_notification_sent(user_id, delivery_date)
    if not marked:
        lazy_logger.logger.warning(
            f"notification_worker failed to persist delivery for user={user_id}"
        )


async def _process_notification_user(
    user,
    *,
    bot,
    notification_service: NotificationService,
    schedule_service: ScheduleService,
    delivery_date: str,
    now: datetime.datetime,
    semaphore: asyncio.Semaphore,
):
    async with semaphore:
        try:
            lazy_logger.logger.info(
                f"notification_worker processing user={user.id} "
                f"type={user.notify_type} uid={user.notify_uid}"
            )

            item = SearchItem(
                type=user.notify_type,
                uid=int(user.notify_uid),
                name=user.notify_name or "",
            )
            schedule = await schedule_service.get_schedule(item)

            if schedule is None:
                lazy_logger.logger.warning(
                    f"notification_worker schedule fetch failed for user={user.id}"
                )
                await bot.send_message(
                    chat_id=user.id,
                    text="⚠️ Не удалось получить расписание для рассылки. Попробуйте позже.",
                )
                await _mark_notification_sent(
                    notification_service, user.id, delivery_date
                )
                return

            tomorrow = now.date() + datetime.timedelta(days=1)
            lessons = schedule_service.get_lessons(schedule, [tomorrow])

            header = (
                f"🔔 Напоминание на завтра\n"
                f"ℹ️ Расписание: {item.name}\n"
                f"📅 Дата: {tomorrow.strftime('%d.%m.%Y')}"
            )

            if not lessons:
                lazy_logger.logger.info(
                    f"notification_worker user={user.id}: no lessons for tomorrow"
                )
                await bot.send_message(
                    chat_id=user.id, text=header + "\n\nНа завтра пар нет ✅"
                )
                await _mark_notification_sent(
                    notification_service, user.id, delivery_date
                )
                return

            blocks = format_outputs(lessons, {"item": item})
            await _send_blocks(bot, user.id, header, blocks)

            lazy_logger.logger.info(
                f"notification_worker sent tomorrow schedule to user={user.id}"
            )
            await _mark_notification_sent(notification_service, user.id, delivery_date)
        except Exception as e:
            lazy_logger.logger.exception(
                f"notification_worker error for user={user.id}: {e}"
            )


async def _ask_time(message: Message, state: FSMContext, selected_item: SearchItem):
    await state.set_state(NotificationStates.awaiting_time)
    await state.update_data(notify_item=selected_item.model_dump(), notify_items=None)
    await message.answer(
        "⏰ Введите время рассылки в формате `HH:MM` (например, `21:30`).\n"
        "Я буду присылать расписание на завтра по выбранному расписанию."
    )


async def _process_notify_query(
    message: Message,
    state: FSMContext,
    query: str,
    schedule_service: ScheduleService,
):
    schedule_items = await schedule_service.search(query)

    if schedule_items is None or len(schedule_items) == 0:
        await message.answer(
            "❌ По этому запросу расписание не найдено. Попробуйте другой запрос."
        )
        return

    if len(schedule_items) == 1:
        await _ask_time(message, state, schedule_items[0])
        return

    await state.set_state(NotificationStates.awaiting_item)
    await state.update_data(
        notify_items=[item.model_dump() for item in schedule_items], notify_item=None
    )

    await message.answer(
        "ℹ️ Найдено несколько вариантов. Выберите нужное расписание:",
        reply_markup=construct.construct_item_markup(schedule_items),
    )


@router.message(Command("notify"))
@inject
async def notify_start(
    message: Message,
    state: FSMContext,
    user_service: FromDishka[UserService],
    schedule_service: FromDishka[ScheduleService],
):
    if message.from_user is None or message.text is None:
        return

    await user_service.ensure_user(message.from_user)
    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) > 1 and command_parts[1].strip():
        await _process_notify_query(
            message,
            state,
            command_parts[1].strip(),
            schedule_service,
        )
        return

    await state.set_state(NotificationStates.awaiting_query)
    await state.update_data(notify_item=None, notify_items=None)
    await message.answer(
        "ℹ️ Введите запрос расписания после /notify или следующим сообщением.\n"
        "Пример: `Карпов` или `ИКБО-20-23`."
    )


@router.message(
    StateFilter(NotificationStates.awaiting_query), F.text & ~F.text.startswith("/")
)
@inject
async def notify_query_input(
    message: Message,
    state: FSMContext,
    schedule_service: FromDishka[ScheduleService],
):
    if message.text is None:
        return

    await _process_notify_query(message, state, message.text.strip(), schedule_service)


@router.message(
    StateFilter(NotificationStates.awaiting_item), F.text & ~F.text.startswith("/")
)
@inject
async def notify_item_text_fallback(
    message: Message,
    state: FSMContext,
    schedule_service: FromDishka[ScheduleService],
):
    if message.text is None:
        return

    await _process_notify_query(message, state, message.text.strip(), schedule_service)


@router.callback_query(StateFilter(NotificationStates.awaiting_item), F.data)
async def notify_item_pick(callback, state: FSMContext):
    data = await state.get_data()
    raw_items = data.get("notify_items") or []
    schedule_items = []

    for raw_item in raw_items:
        try:
            schedule_items.append(SearchItem(**raw_item))
        except Exception:
            continue

    if callback.data == "back":
        await state.set_state(NotificationStates.awaiting_query)
        await callback.message.edit_text(
            "ℹ️ Введите новый запрос расписания для рассылки:"
        )
        await callback.answer()
        return

    if ":" not in callback.data:
        await callback.answer(text="❌ Неверный выбор", show_alert=True)
        return

    selected_type, selected_uid = callback.data.split(":", 1)
    selected_item = None
    for item in schedule_items:
        if item.type == selected_type and str(item.uid) == selected_uid:
            selected_item = item
            break

    if selected_item is None:
        await callback.answer(
            text="❌ Вариант не найден, попробуйте ещё раз", show_alert=True
        )
        return

    await callback.answer()
    await callback.message.edit_text(
        f"✅ Выбрано: {selected_item.name}\n"
        "Теперь укажите время уведомления в формате HH:MM"
    )
    await _ask_time(callback.message, state, selected_item)


@router.message(
    StateFilter(NotificationStates.awaiting_time), F.text & ~F.text.startswith("/")
)
@inject
async def notify_set_time(
    message: Message,
    state: FSMContext,
    notification_service: FromDishka[NotificationService],
):
    if message.from_user is None or message.text is None:
        return

    time_value = message.text.strip()

    if not TIME_PATTERN.fullmatch(time_value):
        await message.answer(
            "❌ Неверный формат времени. Используйте `HH:MM`, например `08:15`."
        )
        return

    data = await state.get_data()
    raw_item = data.get("notify_item")
    selected_item = _extract_item(raw_item)

    if selected_item is None:
        await state.clear()
        await message.answer(
            "❌ Не удалось определить выбранное расписание. Повторите команду /notify."
        )
        return

    await notification_service.set_notification(
        message.from_user.id, time_value, selected_item
    )
    await state.clear()

    await message.answer(
        f"✅ Рассылка на завтра включена.\n"
        f"Расписание: {selected_item.name}\n"
        f"Время: {time_value}\n\n"
        "Чтобы отключить: /notifyoff"
    )


@router.message(Command("notifyoff"))
@inject
async def notify_off(
    message: Message,
    state: FSMContext,
    notification_service: FromDishka[NotificationService],
):
    if message.from_user is None:
        return

    await notification_service.disable_notification(message.from_user.id)
    await state.clear()
    await message.answer("✅ Рассылка отключена.")


async def notification_worker(
    bot,
    notification_service: NotificationService,
    schedule_service: ScheduleService,
):
    lazy_logger.logger.info("notification_worker started")
    semaphore = asyncio.Semaphore(NOTIFY_CONCURRENCY)

    while True:
        started_at = _get_current_msk_time()
        delivery_date = started_at.date().isoformat()
        current_time = started_at.strftime("%H:%M")

        users = await notification_service.get_due_notification_users(
            current_time, delivery_date
        )
        if users:
            lazy_logger.logger.info(
                f"notification_worker tick {current_time}: {len(users)} user(s) due"
            )

            tasks = [
                asyncio.create_task(
                    _process_notification_user(
                        user,
                        bot=bot,
                        notification_service=notification_service,
                        schedule_service=schedule_service,
                        delivery_date=delivery_date,
                        now=started_at,
                        semaphore=semaphore,
                    )
                )
                for user in users
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for user, result in zip(users, results):
                if isinstance(result, Exception):
                    lazy_logger.logger.exception(
                        f"notification_worker gathered task failed for user={user.id}: {result}"
                    )

        finished_at = _get_current_msk_time()
        elapsed = (finished_at - started_at).total_seconds()
        await asyncio.sleep(max(1, NOTIFY_POLL_INTERVAL_SECONDS - elapsed))


def init_handlers(dispatcher):
    dispatcher.include_router(router)
