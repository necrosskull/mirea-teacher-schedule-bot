import datetime
import json

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.db.database import insert_new_user
from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_schedule
from bot.fetch.search import search_schedule
from bot.handlers import send as send
from bot.handlers import states as st
from bot.logs.lazy_logger import lazy_logger


async def get_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Реакция бота на получение запроса от пользователя
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """
    if update.message and update.message.via_bot:
        return
    elif update.edited_message and update.edited_message.via_bot:
        return

    insert_new_user(update, context)

    user_query = update.message.text
    lazy_logger.logger.info(
        json.dumps(
            {
                "type": "request",
                "query": user_query.lower(),
                **update.message.from_user.to_dict(),
            },
            ensure_ascii=False,
        )
    )

    if context.bot_data["maintenance_mode"]:
        await maintenance_message(update, context)
        return

    if len(user_query) < 3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Слишком короткий запрос\nПопробуйте еще раз",
        )
        return

    if user_query.lower().startswith("ауд"):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ Для поиска по аудиториям, просто введите её название, например: `Г-212`",
            parse_mode="Markdown",
        )
        return

    schedule_items = await search_schedule(user_query)

    if schedule_items is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Не нашлось результатов по вашему запросу\nПопробуйте еще раз",
        )
        return

    if len(schedule_items) > 1:
        context.user_data["available_items"] = schedule_items
        return await send.send_item_clarity(update, context, True)

    elif len(schedule_items) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Не нашлось результатов по вашему запросу\nПопробуйте еще раз",
            parse_mode="Markdown",
        )

    else:
        context.user_data["available_items"] = None
        context.user_data["item"] = schedule_items[0]
        context.user_data["schedule"] = await get_schedule(schedule_items[0])

        return await send.send_week_selector(update, context, True)


async def got_item_clarification_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if await deny_old_message(update, context, query=query):
        return

    if query.data == "back":
        return await send.resend_name_input(update, context)

    type, uid = query.data.split(":")

    schedule_items: list[SearchItem] = context.user_data["available_items"]

    selected_item = None
    for item in schedule_items:
        if item.type == type and item.uid == int(uid):
            selected_item: SearchItem = item
            break

    if selected_item not in context.user_data["available_items"]:
        await update.callback_query.answer(
            text="Ошибка, сделайте новый запрос", show_alert=True
        )

    context.user_data["item"] = selected_item
    clarified_schedule = await get_schedule(selected_item)
    context.user_data["schedule"] = clarified_schedule

    await query.answer()

    return await send.send_week_selector(update, context)


async def got_week_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query

    if await deny_old_message(update, context, query=query):
        return

    selected_button = query.data

    if selected_button == "back":
        if context.user_data["available_items"] is None:
            return await send.resend_name_input(update, context)

        return await send.send_item_clarity(update, context)

    elif selected_button == "today":
        today = datetime.date.today()
        context.user_data["date"] = today
        context.user_data["week"] = None

        return await send.send_result(update, context)

    elif selected_button == "tomorrow":
        tommorow = datetime.date.today() + datetime.timedelta(days=1)
        context.user_data["date"] = tommorow
        context.user_data["week"] = None

        return await send.send_result(update, context)

    elif selected_button.isdigit():
        selected_week = int(selected_button)
        context.user_data["week"] = selected_week

        return await send.send_day_selector(update, context)

    else:
        await update.callback_query.answer(
            text="Ошибка, ожидается неделя", show_alert=False
        )

        return st.GETWEEK


async def got_day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Реакция бота на выбор дня недели, предоставленный пользователю, в состоянии GETDAY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query
    show_week = False
    if await deny_old_message(update, context, query=query):
        return

    selected_button = query.data

    if selected_button == "chill":
        await update.callback_query.answer(text="В этот день пар нет.", show_alert=True)

        return st.GETDAY

    if selected_button == "back":
        return await send.send_week_selector(update, context)

    if selected_button == "week":
        selected_day = None
        show_week = True

    else:
        selected_day = selected_button
        context.user_data["date"] = selected_day

    try:
        await send.send_result(update, context, show_week=show_week)

    except BadRequest:
        await update.callback_query.answer(
            text="Вы уже выбрали этот день", show_alert=False
        )
    else:
        await query.answer()

    return st.GETDAY


async def deny_old_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query=None
):
    message_id = None

    if query.inline_message_id:
        message_id = query.inline_message_id
    if query.message:
        message_id = query.message.message_id

    if context.user_data["message_id"] != message_id:
        await query.answer(
            text="Это сообщение не относится к вашему текущему запросу, повторите ваш запрос!",
            show_alert=True,
        )
        return True


async def maintenance_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    maintenance_text = (
        context.bot_data["maintenance_message"]
        if context.bot_data["maintenance_message"]
        else None
    )

    text = (
        f"{maintenance_text}"
        if maintenance_text
        else "Бот находится на техническом обслуживании, скоро всё заработает!"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
    )


def init_handlers(application: Application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, get_query_handler, block=False
            ),
        ],
        states={
            st.ITEM_CLARIFY: [
                CallbackQueryHandler(got_item_clarification_handler, block=False)
            ],
            st.GETDAY: [CallbackQueryHandler(got_day_handler, block=False)],
            st.GETWEEK: [CallbackQueryHandler(got_week_handler, block=False)],
        },
        fallbacks=[
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, get_query_handler, block=False
            ),
        ],
    )
    application.add_handler(conv_handler)
