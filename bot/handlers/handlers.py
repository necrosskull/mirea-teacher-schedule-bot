import datetime
import json
from typing import Any
import re
import requests
import bot.formats.formatting as formatting
import bot.handlers.send as send
import bot.handlers.fetch as fetch
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    Filters,
    MessageHandler
)

import bot.lazy_logger as logger

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, BACK, GETROOM, ROOM_CLARIFY = range(7)


def got_name_handler(update: Update, context: CallbackContext) -> int:
    """
    Реакция бота на получение фамилии преподавателя при состоянии GETNAME
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """
    context.user_data["state"] = "get_name"
    try:
        if update.message.via_bot:
            return ConversationHandler.END

    except AttributeError:
        return ConversationHandler.END

    inputted_teacher = update.message.text
    logger.lazy_logger.info(json.dumps({"type": "request",
                                        "query": inputted_teacher.lower(),
                                        **update.message.from_user.to_dict()},
                                       ensure_ascii=False))

    if len(inputted_teacher) < 2:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Слишком короткий запрос\nПопробуйте еще раз")

    teacher = formatting.normalize_teachername(inputted_teacher)

    teacher_schedule = fetch.fetch_schedule_by_name(teacher)

    if teacher_schedule:
        context.user_data["schedule"] = teacher_schedule
        available_teachers = formatting.check_same_surnames(teacher_schedule, teacher)

        if len(available_teachers) > 1:
            context.user_data["available_teachers"] = available_teachers
            return send.send_teacher_clarity(update, context, True)

        elif len(available_teachers) == 0:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ошибка при определении ФИО преподавателя. Повторите попытку, изменив запрос.\n" +
                     "Например введите только фамилию преподавателя.\n\n"
                     "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
                parse_mode="Markdown")

        else:
            context.user_data["available_teachers"] = None
            context.user_data['teacher'] = available_teachers[0]
            context.user_data["schedule"] = fetch.fetch_schedule_by_name(
                available_teachers[0])

            return send.send_week_selector(update, context, True)

    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Преподаватель не найден\nПопробуйте еще раз\n\nУбедитесь, что преподаватель указан в формате "
                 "*Иванов* или *Иванов И.И.*\n\n"
                 "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
            parse_mode="Markdown")


def got_teacher_clarification_handler(
        update: Update,
        context: CallbackContext):
    """
    Реакция бота на получение фамилии преподавателя при уточнении, при состоянии TEACHER_CLARIFY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    chosed_teacher = update.callback_query.data

    if chosed_teacher == "back":
        return send.resend_name_input(update, context)

    if chosed_teacher not in context.user_data['available_teachers']:
        update.callback_query.answer(
            text="Ошибка, сделайте новый запрос",
            show_alert=True)

    context.user_data['teacher'] = chosed_teacher
    clarified_schedule = fetch.fetch_schedule_by_name(chosed_teacher)
    context.user_data['schedule'] = clarified_schedule

    return send.send_week_selector(update, context)


def got_room_clarification_handler(
        update: Update,
        context: CallbackContext):
    """
    Реакция бота на получение аудитории при состоянии ROOM_CLARIFY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    chosen_room = update.callback_query.data
    context.user_data['room_id'] = chosen_room

    for room in context.user_data['available_rooms']:
        room_name, room_id = room.split(':')
        if room_id == chosen_room:
            context.user_data['room'] = room_name

    if chosen_room == "back":
        return send.resend_name_input(update, context)

    if chosen_room != context.user_data['room_id']:
        update.callback_query.answer(
            text="Ошибка, сделайте новый запрос",
            show_alert=True)

    clarified_schedule = fetch.fetch_room_schedule_by_id(chosen_room)
    context.user_data['schedule'] = clarified_schedule

    return send.send_week_selector(update, context)


def got_week_handler(update: Update, context: CallbackContext) -> Any | None:
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    selected_button = update.callback_query.data

    if selected_button == "back":
        if context.user_data['state'] == "get_room":
            if context.user_data['available_rooms'] is not None:
                return send.send_room_clarity(update, context)
            else:
                return send.resend_name_input(update, context)
        else:

            if context.user_data['available_teachers'] is not None:

                return send.send_teacher_clarity(update, context)

            else:
                return send.resend_name_input(update, context)

    elif selected_button == "today" or selected_button == "tomorrow":
        today = datetime.date.today().weekday()
        req = requests.get(
            "https://schedule.mirea.ninja/api/schedule/current_week").json()
        week = req["week"]

        if selected_button == "tomorrow":
            if today == 6:
                week += 1  # Корректировка недели, в случае если происходит переход недели

            today = (
                    datetime.date.today() +
                    datetime.timedelta(
                        days=1)).weekday()

        if today == 6:
            update.callback_query.answer("В выбранный день пар нет")

            return GETWEEK

        today += 1  # Корректировка дня с 0=пн на 1=пн
        context.user_data["week"] = week
        context.user_data["day"] = today

        return send.send_result(update, context)

    if selected_button.isdigit():
        selected_week = int(selected_button)
        context.user_data["week"] = selected_week

        return send.send_day_selector(update, context)

    else:
        update.callback_query.answer(
            text="Ошибка, ожидается неделя",
            show_alert=False)

        return GETWEEK


def got_day_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на выбор дня недели, предоставленный пользователю, в состоянии GETDAY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    selected_button = update.callback_query.data

    if selected_button == "chill":
        update.callback_query.answer(
            text="В этот день пар нет.", show_alert=True)

        return GETDAY

    if selected_button == "back":
        return send.send_week_selector(update, context)

    if selected_button == "week":
        selected_day = -1
        context.user_data["day"] = selected_day

    elif selected_button.isdigit():
        selected_day = int(selected_button)
        context.user_data["day"] = selected_day

    else:
        update.callback_query.answer(
            text="Ошибка, ожидается день недели",
            show_alert=False)

        return GETDAY

    try:
        return send.send_result(update, context)

    except Exception as e:
        update.callback_query.answer(
            text="Вы уже выбрали этот день",
            show_alert=False)

    return GETDAY


def got_room_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на получение информации о выбранной аудитории в состоянии GETROOM
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    context.user_data["state"] = "get_room"
    room = update.message.text[4:].title()

    logger.lazy_logger.info(json.dumps({"type": "request",
                                        "query": update.message.text.lower(),
                                        **update.message.from_user.to_dict()},
                                       ensure_ascii=False))

    room_schedule = fetch.fetch_room_id_by_name(room)

    if room_schedule:
        context.user_data["schedule"] = room_schedule
        available_rooms = formatting.check_same_rooms(fetch.fetch_room_id_by_name(room), room)

        if len(available_rooms) > 1:
            context.user_data["available_rooms"] = available_rooms
            return send.send_room_clarity(update, context, True)

        elif len(available_rooms) == 0:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Аудитория не найдена, попробуйте еще раз")

        else:
            context.user_data["available_rooms"] = None
            room_name, room_id = available_rooms[0].split(':')

            context.user_data["room"] = room_name
            context.user_data["room_id"] = room_id

            context.user_data["schedule"] = fetch.fetch_room_schedule_by_id(room_id)
            return send.send_week_selector(update, context, True)

    else:
        update.message.reply_text(
            "Аудитория не найдена, попробуйте еще раз")


def init_handlers(dispatcher):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(pattern=re.compile(r'ауд (.+)', re.IGNORECASE)), got_room_handler,
                           run_async=True),
            MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True),
        ],
        states={
            GETDAY: [CallbackQueryHandler(got_day_handler, run_async=True)],
            GETWEEK: [CallbackQueryHandler(got_week_handler, run_async=True)],
            TEACHER_CLARIFY: [CallbackQueryHandler(got_teacher_clarification_handler, run_async=True)],
            ROOM_CLARIFY: [CallbackQueryHandler(got_room_clarification_handler, run_async=True)]
        },
        fallbacks=[
            MessageHandler(Filters.regex(pattern=re.compile(r'ауд (.+)', re.IGNORECASE)), got_room_handler,
                           run_async=True),
            MessageHandler(Filters.text, got_name_handler, run_async=True),
        ],
    )

    dispatcher.add_handler(conv_handler)
