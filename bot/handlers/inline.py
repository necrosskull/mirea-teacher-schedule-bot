import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    ChosenInlineResult,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from dishka.integrations.aiogram import FromDishka, inject

import bot.handlers.construct as construct
import bot.handlers.handler as handler
import bot.logs.lazy_logger as logger
from bot.fetch.models import SearchItem
from bot.handlers.context import bot_data, get_user_data
from bot.handlers import states as st
from bot.service import ScheduleService, UserService

router = Router()


@router.inline_query()
@inject
async def handle_inline_query(
    inline_query: InlineQuery,
    user_service: FromDishka[UserService],
    schedule_service: FromDishka[ScheduleService],
):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """

    if bot_data.get("maintenance_mode", False):
        return

    if inline_query.from_user is None:
        return

    if len(inline_query.query) > 2:

        logger.lazy_logger.logger.info(
            json.dumps(
                {
                    "type": "query",
                    "queryId": inline_query.id,
                    "query": inline_query.query.lower(),
                    **inline_query.from_user.model_dump(),
                },
                ensure_ascii=False,
            )
        )

    query = inline_query.query.lower()

    await handle_query(inline_query, query, user_service, schedule_service)


async def handle_query(
    inline_query: InlineQuery,
    query: str,
    user_service: UserService,
    schedule_service: ScheduleService,
):
    inline_results = []
    schedule_items: list[SearchItem] = []
    description = ""
    favorite = await user_service.get_favorite(inline_query.from_user.id)

    if favorite:
        description = "Сохраненное расписание"
        schedule_items = await schedule_service.search(favorite) or []

    if len(query) > 2:
        description = "Нажми, чтобы посмотреть расписание"
        inline_results = []
        schedule_items = await schedule_service.search(query) or []

    for item in schedule_items:
        name = item.name
        if item.type == "teacher":
            name_parts = item.name.split()

            if len(name_parts) > 1:
                last_name = name_parts[0]

                # Для запроса вида "Иванов И.И. или Иванов И.И"
                if (
                    name_parts[1][-1] == "."
                    or len(name_parts[1]) > 1
                    and name_parts[1][-2] == "."
                ):
                    initials = name_parts[1]
                else:
                    # Для запроса вида "Иванов Иван Иванович и прочих"
                    initials = "".join([part[0] + "." for part in name_parts[1:3]])

                name = last_name + " " + initials
        id_str = f"{item.type}:{item.uid}:{name}"

        inline_results.append(
            InlineQueryResultArticle(
                id=id_str,
                title=item.name,
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=f"ℹ️ Выбрано расписание: {item.name}!\n"
                    + "🗓️ Выберите неделю:"
                ),
                reply_markup=construct.construct_weeks_markup(),
            )
        )

    return await inline_query.answer(
        inline_results,
        cache_time=5,
        is_personal=True,
    )


@router.chosen_inline_result()
@inject
async def answer_inline_handler(chosen_inline_result: ChosenInlineResult, state: FSMContext):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if chosen_inline_result is not None and chosen_inline_result.from_user is not None:
        parts = chosen_inline_result.result_id.split(":", 2)
        if len(parts) != 3:
            return
        item_type, uid, name = parts

        selected_item = SearchItem(type=item_type, uid=int(uid), name=name)

        persistent_data = await get_user_data(chosen_inline_result.from_user.id)
        inline_sessions = persistent_data.get("inline_sessions", {})

        inline_sessions[chosen_inline_result.inline_message_id] = {
            "item": selected_item,
            "available_items": None,
            "schedule": None,
            "inline_message_id": chosen_inline_result.inline_message_id,
            "inline_message_ids": [chosen_inline_result.inline_message_id],
            "message_id": chosen_inline_result.inline_message_id,
            "step": st.GETWEEK,
        }

        if len(inline_sessions) > 30:
            keys = list(inline_sessions.keys())[-30:]
            inline_sessions = {key: inline_sessions[key] for key in keys}

        persistent_data["inline_sessions"] = inline_sessions

    return


@router.callback_query(F.inline_message_id)
@inject
async def inline_dispatcher(
    callback: CallbackQuery,
    schedule_service: FromDishka[ScheduleService],
):
    """
    Обработка вызовов в чатах на основании Callback вызова
    """
    if callback.from_user is None:
        return

    persistent_data = await get_user_data(callback.from_user.id)

    inline_sessions = persistent_data.get("inline_sessions", {})

    if callback.inline_message_id not in inline_sessions:
        await deny_inline_usage(callback)
        return

    user_data = inline_sessions[callback.inline_message_id]

    user_data["schedule"] = await schedule_service.get_schedule(user_data["item"])

    if user_data.get("step") == st.GETWEEK:
        target = await handler.got_week_handler(callback, user_data)
    elif user_data.get("step") == st.GETDAY:
        target = await handler.got_day_handler(callback, user_data)
    else:
        await deny_inline_usage(callback)
        return

    if target == st.GETWEEK:
        user_data["step"] = st.GETWEEK
    elif target == st.GETDAY:
        user_data["step"] = st.GETDAY

    session_to_store = dict(user_data)
    session_to_store.pop("schedule", None)
    inline_sessions[callback.inline_message_id] = session_to_store
    persistent_data["inline_sessions"] = inline_sessions

    return


async def deny_inline_usage(callback: CallbackQuery):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    await callback.answer(
        text="Вы не можете использовать это меню, т.к. оно не относится к вашему запросу",
        show_alert=True,
    )
    return


def init_handlers(dispatcher):
    dispatcher.include_router(router)
