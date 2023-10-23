import datetime
import json
from typing import Any
import re
import bot.formats.formatting as formatting
import bot.handlers.send as send
import bot.handlers.fetch as fetch
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    MessageHandler
)

import bot.lazy_logger as logger
from bot.db.database import insert_new_user
from bot.schedule.week import get_current_week_number

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, GETROOM, ROOM_CLARIFY = range(6)


async def got_name_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на получение фамилии преподавателя при состоянии GETNAME
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """
    if update.message and update.message.via_bot:
        return
    elif update.edited_message and update.edited_message.via_bot:
        return

    insert_new_user(update, context)

    if context.bot_data["maintenance_mode"]:
        await maintenance_message(update, context)
        return

    context.user_data["state"] = "get_name"

    inputted_teacher = update.message.text
    logger.lazy_logger.info(json.dumps({"type": "request",
                                        "query": inputted_teacher.lower(),
                                        **update.message.from_user.to_dict()},
                                       ensure_ascii=False))

    if len(inputted_teacher) < 2:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Слишком короткий запрос\nПопробуйте еще раз")

    teacher = formatting.normalize_teachername(inputted_teacher)

    teacher_schedule = fetch.fetch_schedule_by_name(teacher)

    modified_name = None

    if not teacher_schedule:
        modified_name = formatting.replace_letters_in_teacher_name(teacher)
        teacher_schedule = fetch.fetch_schedule_by_name(modified_name)

    if teacher_schedule:
        context.user_data["schedule"] = teacher_schedule

        fixed_teacher = modified_name if modified_name else teacher
        available_teachers = formatting.check_same_surnames(teacher_schedule, fixed_teacher)

        if len(available_teachers) > 1:
            context.user_data["available_teachers"] = available_teachers
            return await send.send_teacher_clarity(update, context, True)

        elif len(available_teachers) == 0:
            await context.bot.send_message(
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

            return await send.send_week_selector(update, context, True)

    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Преподаватель не найден\nПопробуйте еще раз\n\nУбедитесь, что преподаватель указан в формате "
                 "*Иванов* или *Иванов И.И.*\n\n"
                 "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
            parse_mode="Markdown")


async def got_teacher_clarification_handler(
        update: Update,
        context: CallbackContext):
    """
    Реакция бота на получение фамилии преподавателя при уточнении, при состоянии TEACHER_CLARIFY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query

    chosed_teacher = update.callback_query.data

    if chosed_teacher == "back":
        return await send.resend_name_input(update, context)

    if chosed_teacher not in context.user_data['available_teachers']:
        await update.callback_query.answer(
            text="Ошибка, сделайте новый запрос",
            show_alert=True)

    context.user_data['teacher'] = chosed_teacher
    clarified_schedule = fetch.fetch_schedule_by_name(chosed_teacher)
    context.user_data['schedule'] = clarified_schedule

    await query.answer()

    return await send.send_week_selector(update, context)


async def got_room_clarification_handler(
        update: Update,
        context: CallbackContext):
    """
    Реакция бота на получение аудитории при состоянии ROOM_CLARIFY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query

    chosen_room = update.callback_query.data
    context.user_data['room_id'] = chosen_room

    for room in context.user_data['available_rooms']:
        room_name, room_id = room.split(':')
        if room_id == chosen_room:
            context.user_data['room'] = room_name

    if chosen_room == "back":
        return await send.resend_name_input(update, context)

    if chosen_room != context.user_data['room_id']:
        await update.callback_query.answer(
            text="Ошибка, сделайте новый запрос",
            show_alert=True)

    clarified_schedule = fetch.fetch_room_schedule_by_id(chosen_room)
    context.user_data['schedule'] = clarified_schedule

    await query.answer()

    return await send.send_week_selector(update, context)


async def got_week_handler(update: Update, context: CallbackContext) -> Any | None:
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query

    selected_button = update.callback_query.data

    if selected_button == "back":
        if context.user_data['state'] == "get_room":

            if context.user_data['available_rooms'] is not None:
                return await send.send_room_clarity(update, context)
            else:
                return await send.resend_name_input(update, context)

        elif context.user_data['state'] == "get_group":
            return await send.resend_name_input(update, context)

        else:

            if context.user_data['available_teachers'] is not None:

                return await send.send_teacher_clarity(update, context)

            else:
                return await send.resend_name_input(update, context)

    elif selected_button == "today" or selected_button == "tomorrow":
        today = datetime.date.today().weekday()
        week = get_current_week_number()

        if selected_button == "tomorrow":
            if today == 6:
                week += 1  # Корректировка недели, в случае если происходит переход недели

            today = (
                    datetime.date.today() +
                    datetime.timedelta(
                        days=1)).weekday()

        if today == 6:
            await update.callback_query.answer("В выбранный день пар нет")

            return GETWEEK

        today += 1  # Корректировка дня с 0=пн на 1=пн
        context.user_data["week"] = week
        context.user_data["day"] = today

        return await send.send_result(update, context, None)

    if selected_button.isdigit():
        selected_week = int(selected_button)
        context.user_data["week"] = selected_week

        return await send.send_day_selector(update, context)

    else:
        await update.callback_query.answer(
            text="Ошибка, ожидается неделя",
            show_alert=False)

        return GETWEEK


async def got_day_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на выбор дня недели, предоставленный пользователю, в состоянии GETDAY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    query = update.callback_query

    selected_button = update.callback_query.data

    if selected_button == "chill":
        await update.callback_query.answer(
            text="В этот день пар нет.", show_alert=True)

        return GETDAY

    if selected_button == "back":
        return await send.send_week_selector(update, context)

    if selected_button == "week":
        selected_day = -1
        context.user_data["day"] = selected_day

    elif selected_button.isdigit():
        selected_day = int(selected_button)
        context.user_data["day"] = selected_day

    else:
        await update.callback_query.answer(
            text="Ошибка, ожидается день недели",
            show_alert=False)

        return GETDAY

    try:
        await send.send_result(update, context, selected_day)

    except Exception as e:
        await update.callback_query.answer(
            text="Вы уже выбрали этот день",
            show_alert=False)
    else:
        await query.answer()

    return GETDAY


async def got_room_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на получение информации о выбранной аудитории в состоянии GETROOM
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    if update.message and update.message.via_bot:
        return
    elif update.edited_message and update.edited_message.via_bot:
        return

    insert_new_user(update, context)

    if context.bot_data["maintenance_mode"]:
        await maintenance_message(update, context)
        return

    context.user_data["state"] = "get_room"
    room = update.message.text[4:].lower()

    if len(room) < 3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Слишком короткий запрос\nПопробуйте еще раз")
        return

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
            return await send.send_room_clarity(update, context, True)

        elif len(available_rooms) == 0:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Аудитория не найдена, попробуйте еще раз")

        else:
            context.user_data["available_rooms"] = None
            room_name, room_id = available_rooms[0].split(':')

            context.user_data["room"] = room_name
            context.user_data["room_id"] = room_id

            context.user_data["schedule"] = fetch.fetch_room_schedule_by_id(room_id)
            return await send.send_week_selector(update, context, True)

    else:
        await update.message.reply_text(
            "Аудитория не найдена, попробуйте еще раз")


async def got_group_handler(update: Update, context: CallbackContext):
    if update.message and update.message.via_bot:
        return
    elif update.edited_message and update.edited_message.via_bot:
        return

    insert_new_user(update, context)

    if context.bot_data["maintenance_mode"]:
        await maintenance_message(update, context)
        return

    context.user_data["state"] = "get_group"

    inputted_group = update.message.text.upper()

    logger.lazy_logger.info(json.dumps({"type": "request",
                                        "query": inputted_group,
                                        **update.message.from_user.to_dict()},
                                       ensure_ascii=False))

    group_schedule = fetch.fetch_schedule_by_group(inputted_group)

    if group_schedule:
        context.user_data["schedule"] = group_schedule
        context.user_data["group"] = inputted_group
        return await send.send_week_selector(update, context, True)

    else:
        await update.message.reply_text(
            "Группа не найдена, попробуйте еще раз")


async def maintenance_message(update: Update, context: CallbackContext):
    maintenance_text = context.bot_data["maintenance_message"] if context.bot_data["maintenance_message"] else None

    text = f"{maintenance_text}" if maintenance_text else \
        "Бот находится на техническом обслуживании, скоро всё заработает!"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
    )


def init_handlers(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(pattern=re.compile(r'^ауд (.+)', re.IGNORECASE)), got_room_handler,
                           block=False),
            MessageHandler(filters.Regex(pattern=re.compile(r'^[а-я]{4}-\d{2}-\d{2}', re.IGNORECASE)),
                           got_group_handler,
                           block=False),
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_name_handler, block=False),
        ],
        states={
            GETDAY: [CallbackQueryHandler(got_day_handler, block=False)],
            GETWEEK: [CallbackQueryHandler(got_week_handler, block=False)],
            TEACHER_CLARIFY: [CallbackQueryHandler(got_teacher_clarification_handler, block=False)],
            ROOM_CLARIFY: [CallbackQueryHandler(got_room_clarification_handler, block=False)]
        },
        fallbacks=[
            MessageHandler(filters.Regex(pattern=re.compile(r'^ауд (.+)', re.IGNORECASE)), got_room_handler,
                           block=False),
            MessageHandler(filters.Regex(pattern=re.compile(r'^[а-я]{4}-\d{2}-\d{2}', re.IGNORECASE)),
                           got_group_handler,
                           block=False),
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_name_handler, block=False),
        ],
    )

    application.add_handler(conv_handler)
