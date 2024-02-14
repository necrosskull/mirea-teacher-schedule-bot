import json

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
    InlineQueryHandler,
)

import bot.handlers.construct as construct
import bot.handlers.handler as handler
import bot.logs.lazy_logger as logger
from bot.db.database import get_user_favorites
from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_schedule
from bot.fetch.search import search_schedule
from bot.handlers import states as st
from bot.handlers.states import EInlineStep


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """

    if context.bot_data["maintenance_mode"]:
        return

    if len(update.inline_query.query) > 2:
        logger.lazy_logger.logger.info(
            json.dumps(
                {
                    "type": "query",
                    "queryId": update.inline_query.id,
                    "query": update.inline_query.query.lower(),
                    **update.inline_query.from_user.to_dict(),
                },
                ensure_ascii=False,
            )
        )

    inline_query = update.inline_query
    query = inline_query.query.lower()

    await handle_query(update, context, query)


async def handle_query(update: Update, context: CallbackContext, query: str):
    inline_results = []
    schedule_items = []
    description = ""
    favorite = get_user_favorites(update, context)

    if favorite:
        description = "Сохраненное расписание"
        schedule_items: list[SearchItem] = await search_schedule(favorite)

    if len(query) > 2:
        description = "Нажми, чтобы посмотреть расписание"
        inline_results = []
        schedule_items: list[SearchItem] = await search_schedule(query)

    for item in schedule_items:
        inline_results.append(
            InlineQueryResultArticle(
                id=f"{item.type}:{item.uid}",
                title=item.name,
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=f"ℹ️ Выбрано расписание: {item.name}!\n"
                    + "🗓️ Выберите неделю:"
                ),
                reply_markup=construct.construct_weeks_markup(),
            )
        )

    context.user_data["inline_available_items"] = schedule_items
    return await update.inline_query.answer(
        inline_results, cache_time=1, is_personal=True
    )


async def answer_inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if update.chosen_inline_result is not None:
        type, uid = update.chosen_inline_result.result_id.split(":")
        schedule_items: list[SearchItem] = context.user_data["inline_available_items"]

        selected_item = None
        for item in schedule_items:
            if item.type == type and item.uid == int(uid):
                selected_item: SearchItem = item
                break

        context.user_data["item"] = selected_item

        context.user_data["inline_step"] = EInlineStep.ask_week
        context.user_data[
            "inline_message_id"
        ] = update.chosen_inline_result.inline_message_id
        context.user_data["message_id"] = update.chosen_inline_result.inline_message_id

    return


async def inline_dispatcher(update: Update, context: CallbackContext):
    """
    Обработка вызовов в чатах на основании Callback вызова
    """
    if "inline_step" not in context.user_data:
        await deny_inline_usage(update)
        return

    # Если Id сообщения в котором мы нажимаем на кнопки не совпадает с тем, что было сохранено в контексте при вызове
    # меню, то отказываем в обработке

    if (
        update.callback_query.inline_message_id
        and update.callback_query.inline_message_id
        != context.user_data["inline_message_id"]
    ):
        await deny_inline_usage(update)
        return

    status = context.user_data["inline_step"]
    if status == EInlineStep.completed or status == EInlineStep.ask_item:
        await deny_inline_usage(update)
        return

    context.user_data["schedule"] = await get_schedule(context.user_data["item"])

    if status == EInlineStep.ask_week:  # Изначально мы находимся на этапе выбора недели
        context.user_data["available_items"] = None

        target = await handler.got_week_handler(
            update, context
        )  # Обработка выбора недели
        # Затем как только мы выбрали неделю, мы переходим на этап выбора дня
        if target == st.GETDAY:
            context.user_data["inline_step"] = EInlineStep.ask_day

    if status == EInlineStep.ask_day:  # При выборе дня, статус меняется на ask_day
        target = await handler.got_day_handler(update, context)  # Обработка выбора дня

        if (
            target == st.GETWEEK
        ):  # Если пользователь вернулся назад на выбор недели, то мы переходим на этап выбора недели
            context.user_data["inline_step"] = EInlineStep.ask_week

    return


async def deny_inline_usage(update: Update):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    await update.callback_query.answer(
        text="Вы не можете использовать это меню, т.к. оно не относится к вашему запросу",
        show_alert=True,
    )
    return


def init_handlers(application: Application):
    application.add_handler(InlineQueryHandler(handle_inline_query, block=False))
    application.add_handler(
        ChosenInlineResultHandler(answer_inline_handler, block=False)
    )
    application.add_handler(CallbackQueryHandler(inline_dispatcher, block=False))
