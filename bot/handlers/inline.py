import json

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import CallbackContext, InlineQueryHandler, ChosenInlineResultHandler, CallbackQueryHandler

import bot.InlineStep as InlineStep
import bot.handlers.construct as construct
import bot.formats.decode as decode
import bot.handlers.handlers as handlers
import bot.lazy_logger as logger
import bot.formats.formatting as formatting
import bot.handlers.fetch as fetch

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, BACK, GETROOM, ROOM_CLARIFY = range(7)


async def inlinequery(update: Update, context: CallbackContext):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """

    if "ауд" in update.inline_query.query.lower():
        query = update.inline_query.query[4:]
        context.user_data["state"] = "get_room"

        if not query:
            return

        logger.lazy_logger.info(json.dumps(
            {"type": "query",
             "queryId": update.inline_query.id,
             "query": query.lower(),
             **update.inline_query.from_user.to_dict()}, ensure_ascii=False))

        query = query.lower()

        room_schedule = fetch.fetch_room_id_by_name(query)

        if room_schedule is None:
            return

        avaliable_rooms = formatting.check_same_rooms(room_schedule, query)

        if len(avaliable_rooms) == 0:
            return
        context.user_data['available_rooms'] = avaliable_rooms

        inline_results = []

        userid = str(update.inline_query.from_user.id)

        for room in avaliable_rooms[:10]:
            room_name, room_id = room.split(":")
            inline_results.append(InlineQueryResultArticle(
                id=room_id,
                title=room_name,
                description="Нажми, чтобы посмотреть расписание",
                input_message_content=InputTextMessageContent(
                    message_text=f"Выбрана аудитория: {room_name}!\n" +
                                 f"Выберите неделю:"
                ),
                reply_markup=construct.construct_weeks_markup(),
            ))

        await update.inline_query.answer(inline_results, cache_time=10, is_personal=True)

    else:
        context.user_data["state"] = "get_name"
        query = update.inline_query.query

        if not query:
            return

        if len(query) < 3:
            return

        logger.lazy_logger.info(json.dumps(
            {"type": "query",
             "queryId": update.inline_query.id,
             "query": query.lower(),
             **update.inline_query.from_user.to_dict()}, ensure_ascii=False))

        query = query.title()
        teacher_schedule = fetch.fetch_schedule_by_name(query)

        if teacher_schedule is None:
            return

        surnames = formatting.check_same_surnames(teacher_schedule, query)[:10]

        if len(surnames) == 0:
            return

        inline_results = []

        decoded_surnames = decode.decode_teachers(surnames)
        userid = str(update.inline_query.from_user.id)

        for surname, decoded_surname in zip(surnames, decoded_surnames):
            inline_results.append(InlineQueryResultArticle(
                id=surname,
                title=decoded_surname,
                description="Нажми, чтобы посмотреть расписание",
                input_message_content=InputTextMessageContent(
                    message_text=f"Выбран преподаватель: {decoded_surname}!\n" +
                                 f"Выберите неделю:"
                ),
                reply_markup=construct.construct_weeks_markup(),

            ))

        await update.inline_query.answer(inline_results, cache_time=10, is_personal=True)


async def answer_inline_handler(update: Update, context: CallbackContext):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if update.chosen_inline_result is not None:
        if context.user_data["state"] != "get_room":
            context.user_data["teacher"] = update.chosen_inline_result.result_id
        else:
            context.user_data["room_id"] = update.chosen_inline_result.result_id
            for room in context.user_data['available_rooms']:
                room_name, room_id = room.split(':')
                if room_id == update.chosen_inline_result.result_id:
                    context.user_data['room'] = room_name

        context.user_data["inline_step"] = InlineStep.EInlineStep.ask_week
        context.user_data["inline_message_id"] = update.chosen_inline_result.inline_message_id
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

    if update.callback_query.inline_message_id and update.callback_query.inline_message_id != \
            context.user_data["inline_message_id"]:
        await deny_inline_usage(update)
        return

    status = context.user_data["inline_step"]
    if status == InlineStep.EInlineStep.completed or status == InlineStep.EInlineStep.ask_teacher:
        await deny_inline_usage(update)
        return

    if status == InlineStep.EInlineStep.ask_week:
        context.user_data['available_teachers'] = None
        context.user_data['available_rooms'] = None
        if context.user_data["state"] == "get_room":
            context.user_data["schedule"] = fetch.fetch_room_schedule_by_id(context.user_data["room_id"])
        else:
            context.user_data["schedule"] = fetch.fetch_schedule_by_name(
                context.user_data["teacher"])

        target = await handlers.got_week_handler(update, context)

        if target == GETDAY:
            context.user_data["inline_step"] = InlineStep.EInlineStep.ask_day

        elif target == BACK:
            context.user_data["inline_step"] = InlineStep.EInlineStep.ask_day

    if status == InlineStep.EInlineStep.ask_day:
        target = await handlers.got_day_handler(update, context)
        if target == GETWEEK:
            if context.user_data["state"] == "get_room":
                context.user_data["schedule"] = fetch.fetch_room_schedule_by_id(context.user_data["room_id"])
            else:
                context.user_data["schedule"] = fetch.fetch_schedule_by_name(
                    context.user_data["teacher"])
            context.user_data["inline_step"] = InlineStep.EInlineStep.ask_week

        elif target == BACK:
            context.user_data["inline_step"] = InlineStep.EInlineStep.ask_day
        return


async def deny_inline_usage(update: Update):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    await update.callback_query.answer(
        text="Вы не можете использовать это меню, т.к. оно не относится к вашему запросу",
        show_alert=True)
    return


def init_handlers(application):
    application.add_handler(InlineQueryHandler(inlinequery, block=False))
    application.add_handler(ChosenInlineResultHandler(answer_inline_handler, block=False))
    application.add_handler(CallbackQueryHandler(inline_dispatcher, block=False))
