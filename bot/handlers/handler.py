import datetime
import json

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka, inject

from bot.fetch.models import SearchItem
from bot.handlers.context import bot_data, get_user_data
from bot.handlers import send as send
from bot.handlers import states as st
from bot.logs.lazy_logger import lazy_logger
from bot.service import ScheduleService, UserService

router = Router()


def _session_key_from_callback(callback: CallbackQuery) -> str | None:
    if callback.message:
        return str(callback.message.message_id)

    if callback.inline_message_id:
        return callback.inline_message_id

    return None


async def get_query_handler(
    message: Message,
    user_service: UserService,
    schedule_service: ScheduleService,
    fav: str | None = None,
):
    """
    Реакция бота на получение запроса от пользователя
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """
    if message.via_bot:
        return

    await user_service.ensure_user(message.from_user)

    persistent_data = await get_user_data(message.from_user.id)
    sessions = persistent_data.get("sessions", {})
    user_data = {}

    if fav:
        user_query = fav
    else:
        user_query = message.text

    lazy_logger.logger.info(
        json.dumps(
            {
                "type": "request",
                "query": user_query.lower(),
                **message.from_user.model_dump(),
            },
            ensure_ascii=False,
        )
    )

    if bot_data["maintenance_mode"]:
        await maintenance_message(message)
        return

    if len(user_query) < 3:
        await message.answer(
            text="❌ Слишком короткий запрос\nПопробуйте еще раз",
        )
        return

    if user_query.lower().startswith("ауд"):
        await message.answer(
            text="ℹ️ Для поиска по аудиториям, просто введите её название, например: `Г-212`",
        )
        return

    schedule_items = await schedule_service.search(user_query)

    if schedule_items is None:
        await message.answer(
            text="❌ Не нашлось результатов по вашему запросу\nПопробуйте еще раз",
        )
        return

    if len(schedule_items) > 1:
        user_data["available_items"] = schedule_items
        target = await send.send_item_clarity(
            message,
            message.bot,
            user_data,
            True,
            chat_id=message.chat.id,
        )
        user_data["step"] = target

        session_key = str(user_data.get("message_id"))
        session_to_store = dict(user_data)
        session_to_store.pop("schedule", None)
        sessions[session_key] = session_to_store
        persistent_data["sessions"] = sessions
        return target

    elif len(schedule_items) == 0:
        await message.answer(
            text="❌ Не нашлось результатов по вашему запросу\nПопробуйте еще раз",
        )
        return

    else:
        user_data["available_items"] = None
        user_data["item"] = schedule_items[0]
        user_data["schedule"] = await schedule_service.get_schedule(schedule_items[0])
        target = await send.send_week_selector(
            message,
            message.bot,
            user_data,
            True,
            chat_id=message.chat.id,
        )
        user_data["step"] = target

        session_key = str(user_data.get("message_id"))
        session_to_store = dict(user_data)
        session_to_store.pop("schedule", None)
        sessions[session_key] = session_to_store
        persistent_data["sessions"] = sessions
        return target


async def got_item_clarification_handler(
    callback: CallbackQuery,
    user_data: dict,
    schedule_service: ScheduleService,
):
    query = callback

    if await deny_old_message(query, user_data):
        return

    if query.data == "back":
        return await send.resend_name_input(query)

    type, uid = query.data.split(":")

    schedule_items: list[SearchItem] = user_data["available_items"]

    selected_item = None
    for item in schedule_items:
        if item.type == type and item.uid == int(uid):
            selected_item = item
            break

    if selected_item not in schedule_items:
        await query.answer(
            text="Ошибка, сделайте новый запрос", show_alert=True
        )
        return

    user_data["item"] = selected_item
    clarified_schedule = await schedule_service.get_schedule(selected_item)
    user_data["schedule"] = clarified_schedule

    await query.answer()

    target = await send.send_week_selector(query, callback.bot, user_data)
    return target


async def got_week_handler(callback: CallbackQuery, user_data: dict):
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = callback

    if await deny_old_message(query, user_data):
        return

    selected_button = query.data

    if selected_button == "back":
        if user_data["available_items"] is None:
            return await send.resend_name_input(query)

        target = await send.send_item_clarity(query, callback.bot, user_data)
        return target

    elif selected_button == "today":
        today = datetime.date.today()
        user_data["date"] = today
        user_data["week"] = None

        target = await send.send_result(query, callback.bot, user_data)
        return target

    elif selected_button == "tomorrow":
        tommorow = datetime.date.today() + datetime.timedelta(days=1)
        user_data["date"] = tommorow
        user_data["week"] = None

        target = await send.send_result(query, callback.bot, user_data)
        return target

    elif selected_button.isdigit():
        selected_week = int(selected_button)
        user_data["week"] = selected_week

        target = await send.send_day_selector(query, user_data)
        return target

    else:
        await query.answer(
            text="Ошибка, ожидается неделя", show_alert=False
        )

        return st.GETWEEK


async def got_day_handler(callback: CallbackQuery, user_data: dict):
    """
    Реакция бота на выбор дня недели, предоставленный пользователю, в состоянии GETDAY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = callback
    show_week = False
    if await deny_old_message(query, user_data):
        return

    selected_button = query.data

    if selected_button == "chill":
        await query.answer(text="В этот день пар нет.", show_alert=True)

        return st.GETDAY

    if selected_button == "back":
        target = await send.send_week_selector(query, callback.bot, user_data)
        return target

    if selected_button == "week":
        selected_day = None
        show_week = True

    else:
        selected_day = selected_button
        user_data["date"] = selected_day

    try:
        target = await send.send_result(query, callback.bot, user_data, show_week=show_week)

    except TelegramBadRequest:
        await query.answer(
            text="Вы уже выбрали этот день", show_alert=False
        )
        return st.GETDAY
    else:
        await query.answer()

    return target


async def deny_old_message(
    query: CallbackQuery,
    user_data: dict,
):
    if query.inline_message_id:
        inline_ids = set(user_data.get("inline_message_ids", []))
        legacy_inline_id = user_data.get("inline_message_id")
        if legacy_inline_id:
            inline_ids.add(legacy_inline_id)

        if query.inline_message_id not in inline_ids:
            await query.answer(
                text="Это сообщение не относится к вашему текущему запросу, повторите ваш запрос!",
                show_alert=True,
            )
            return True

        return False

    if query.message:
        message_ids = set(user_data.get("message_ids", []))
        legacy_message_id = user_data.get("message_id")
        if legacy_message_id:
            message_ids.add(legacy_message_id)

        if query.message.message_id in message_ids:
            return False

        await query.answer(
            text="Это сообщение не относится к вашему текущему запросу, повторите ваш запрос!",
            show_alert=True,
        )
        return True

    return False


async def maintenance_message(message: Message):
    maintenance_text = (
        bot_data["maintenance_message"]
        if bot_data["maintenance_message"]
        else None
    )

    text = (
        f"{maintenance_text}"
        if maintenance_text
        else "Бот находится на техническом обслуживании, скоро всё заработает!"
    )

    await message.answer(text=text)


@router.message(Command("fav"))
@inject
async def favourite(
    message: Message,
    user_service: FromDishka[UserService],
    schedule_service: FromDishka[ScheduleService],
):
    query = await user_service.get_favorite(message.from_user.id)

    if not query:
        await message.answer(
            text="❌ У вас нет сохраненного расписания\nПопробуйте добавить его с помощью команды /save",
        )
        return

    return await get_query_handler(
        message,
        user_service=user_service,
        schedule_service=schedule_service,
        fav=query,
    )


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
@inject
async def message_dispatcher(
    message: Message,
    user_service: FromDishka[UserService],
    schedule_service: FromDishka[ScheduleService],
):
    await get_query_handler(
        message,
        user_service=user_service,
        schedule_service=schedule_service,
    )


@router.callback_query(StateFilter(None), F.message)
@inject
async def callback_dispatcher(
    callback: CallbackQuery,
    schedule_service: FromDishka[ScheduleService],
):
    persistent_data = await get_user_data(callback.from_user.id)
    sessions = persistent_data.get("sessions", {})

    session_key = _session_key_from_callback(callback)
    if not session_key or session_key not in sessions:
        await callback.answer(
            text="Это сообщение не относится к вашему текущему запросу, повторите ваш запрос!",
            show_alert=True,
        )
        return

    user_data = sessions[session_key]

    if user_data.get("schedule") is None and user_data.get("item") is not None:
        user_data["schedule"] = await schedule_service.get_schedule(user_data["item"])

    step = user_data.get("step")

    if step == st.ITEM_CLARIFY:
        target = await got_item_clarification_handler(
            callback,
            user_data,
            schedule_service=schedule_service,
        )
    elif step == st.GETWEEK:
        target = await got_week_handler(callback, user_data)
    elif step == st.GETDAY:
        target = await got_day_handler(callback, user_data)
    else:
        await callback.answer(
            text="Это сообщение не относится к вашему текущему запросу, повторите ваш запрос!",
            show_alert=True,
        )
        return

    if target:
        user_data["step"] = target

    session_to_store = dict(user_data)
    session_to_store.pop("schedule", None)
    sessions[session_key] = session_to_store
    persistent_data["sessions"] = sessions


def init_handlers(dispatcher):
    dispatcher.include_router(router)
