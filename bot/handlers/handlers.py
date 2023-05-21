import datetime
import json
from typing import Any

import requests
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    Filters,
    MessageHandler
)

from bot.handlers.construct import construct_teacher_markup, construct_weeks_markup, construct_teacher_workdays
from bot.formats.decode import decode_teachers
from bot.formats.formatting import normalize_teachername, format_outputs
from bot.lazy_logger import lazy_logger
from bot.formats.parse import check_same_surnames, merge_weeks_numbers, remove_duplicates_merge_groups_with_same_lesson, \
    parse

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, BACK = range(5)


def got_name_handler(update: Update, context: CallbackContext) -> int:
    """
    Реакция бота на получение фамилии преподавателя при состоянии GETNAME
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """

    try:
        if update.message.via_bot:
            return GETNAME

    except AttributeError:
        return GETNAME

    inputted_teacher = update.message.text
    lazy_logger.info(json.dumps({"type": "request",
                                 "query": inputted_teacher.lower(),
                                 **update.message.from_user.to_dict()},
                                ensure_ascii=False))

    if len(inputted_teacher) < 2:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Слишком короткий запрос\nПопробуйте еще раз")

        return GETNAME

    teacher = normalize_teachername(inputted_teacher)

    teacher_schedule = fetch_schedule_by_name(teacher)

    if teacher_schedule:
        context.user_data["schedule"] = teacher_schedule
        available_teachers = check_same_surnames(teacher_schedule, teacher)

        if len(available_teachers) > 1:
            context.user_data["available_teachers"] = available_teachers
            return send_teacher_clarity(update, context, True)

        elif len(available_teachers) == 0:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ошибка при определении ФИО преподавателя. Повторите попытку, изменив запрос.\n" +
                     "Например введите только фамилию преподавателя.\n\n"
                     "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
                parse_mode="Markdown")

            return GETNAME

        else:
            context.user_data["available_teachers"] = None
            context.user_data['teacher'] = available_teachers[0]
            context.user_data["schedule"] = fetch_schedule_by_name(
                available_teachers[0])

            return send_week_selector(update, context, True)

    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Преподаватель не найден\nПопробуйте еще раз\n\nУбедитесь, что преподаватель указан в формате "
                 "*Иванов* или *Иванов И.И.*\n\n"
                 "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
            parse_mode="Markdown")

        return GETNAME


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
        return resend_name_input(update, context)

    if chosed_teacher not in context.user_data['available_teachers']:
        update.callback_query.answer(
            text="Ошибка, сделайте новый запрос",
            show_alert=True)

        return GETNAME

    context.user_data['teacher'] = chosed_teacher
    clarified_schedule = fetch_schedule_by_name(chosed_teacher)
    context.user_data['schedule'] = clarified_schedule

    return send_week_selector(update, context)


def got_week_handler(update: Update, context: CallbackContext) -> Any | None:
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    selected_button = update.callback_query.data

    if selected_button == "back":
        if context.user_data['available_teachers'] is not None:

            return send_teacher_clarity(update, context)

        else:
            return resend_name_input(update, context)

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

        return send_result(update, context)

    if selected_button.isdigit():
        selected_week = int(selected_button)
        context.user_data["week"] = selected_week

        return send_day_selector(update, context)

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
        return send_week_selector(update, context)

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
        return send_result(update, context)

    except Exception as e:
        update.callback_query.answer(
            text="Вы уже выбрали этот день",
            show_alert=False)

    return GETDAY


def fetch_schedule_by_name(teacher_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param teacher_name: Имя преподавателя
    @return: JSON расписание или None если преподаватель не найден
    """

    url = f"https://timetable.mirea.ru/api/teacher/search/{teacher_name}"

    try:
        response = requests.get(url)
        return response.json() if response.status_code == 200 else None

    except requests.RequestException:
        return None


def send_week_selector(
        update: Update,
        context: CallbackContext,
        firsttime=False):
    """
    Отправка селектора недели. По умолчанию изменяет предыдущее сообщение, но при firsttime=True отправляет в виде
    нового сообщения @param update: Update class of API @param context: CallbackContext of API @param firsttime:
    Впервые ли производится общение с пользователем @return: Статус следующего шага - GETWEEK
    """
    teacher = ", ".join(decode_teachers([context.user_data["teacher"]]))

    if firsttime:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct_weeks_markup()
        )

    else:
        update.callback_query.edit_message_text(
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct_weeks_markup()
        )

    return GETWEEK


def resend_name_input(update: Update, context: CallbackContext):
    """
    Просит ввести имя преподавателя заново
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Статус следующего шага - GETNAME
    """
    update.callback_query.answer(text="Введите новую фамилию", show_alert=True)


def send_teacher_clarity(
        update: Update,
        context: CallbackContext,
        firsttime=False):
    """
    Отправляет список обнаруженных преподавателей. В случае если общение с пользователем не впервые - редактирует
    сообщение, иначе отправляет новое. @param update: Update class of API @param context: CallbackContext of API
    @param firsttime: Впервые ли производится общение с пользователем @return: Статус следующего шага - TEACHER_CLARIFY
    """
    available_teachers = context.user_data["available_teachers"]
    few_teachers_markup = construct_teacher_markup(available_teachers)

    if firsttime:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите преподвателя",
            reply_markup=few_teachers_markup
        )

    else:
        update.callback_query.edit_message_text(
            text="Выберите преподвателя",
            reply_markup=few_teachers_markup
        )

    return TEACHER_CLARIFY


def send_day_selector(update: Update, context: CallbackContext):
    """
    Отправляет селектор дня недели с указанием дней, когда преподаватель не имеет пар.
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Статус следующего шага - GETDAY
    """
    teacher = ", ".join(decode_teachers([context.user_data["teacher"]]))
    week = context.user_data["week"]
    schedule = context.user_data["schedule"]
    teacher_workdays = construct_teacher_workdays(teacher, week, schedule)

    update.callback_query.edit_message_text(
        text=f"Выбран преподаватель: {teacher} \n" +
             f"Выбрана неделя: {week} \n" +
             f"Выберите день",
        reply_markup=teacher_workdays
    )

    return GETDAY


def send_result(update: Update, context: CallbackContext):
    """
    Выводит результат пользователю.
    В user_data["week"] и user_data["day"] должны быть заполнены перед вызовом!
    Если user_data["week"]=-1 - выводится вся неделя
    """
    week = context.user_data["week"]
    weekday = context.user_data["day"]
    schedule_data = context.user_data["schedule"]
    teacher_surname = context.user_data["teacher"]

    parsed_schedule = parse(
        schedule_data,
        weekday,
        week,
        teacher_surname,
        context)

    parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(
        parsed_schedule)

    parsed_schedule = merge_weeks_numbers(parsed_schedule)

    if len(parsed_schedule) == 0:
        update.callback_query.answer(
            text="В этот день пар нет.", show_alert=True)
        return GETWEEK

    blocks_of_text = format_outputs(parsed_schedule, context)

    return telegram_delivery_optimisation(blocks_of_text, update, context)


def telegram_delivery_optimisation(
        blocks: list,
        update: Update,
        context: CallbackContext):
    teacher = context.user_data["teacher"]

    context.user_data["schedule"] = fetch_schedule_by_name(
        context.user_data["teacher"])

    schedule = context.user_data["schedule"]
    week = context.user_data["week"]
    teacher_workdays = construct_teacher_workdays(teacher, week, schedule)

    chunk = ""
    first = True
    for block in blocks:

        if len(chunk) + len(block) <= 4096:
            chunk += block

        else:
            if first:
                if update.callback_query.inline_message_id:
                    update.callback_query.answer(
                        text="Слишком длинное расписание, пожалуйста, воспользуйтесь личными сообщениями бота или "
                             "выберите конкретный день недели", show_alert=True)
                    break

                update.callback_query.edit_message_text(chunk)
                first = False

            else:
                context.bot.send_message(
                    chat_id=update.effective_chat.id, text=chunk)

            chunk = block

    if chunk:
        if first:
            update.callback_query.edit_message_text(
                chunk, reply_markup=teacher_workdays)

        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=chunk,
                reply_markup=teacher_workdays)

    return GETDAY


def init_handlers(dispatcher):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True),
        ],
        states={
            GETNAME: [MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True)],
            GETDAY: [CallbackQueryHandler(got_day_handler, run_async=True)],
            GETWEEK: [CallbackQueryHandler(got_week_handler, run_async=True)],
            TEACHER_CLARIFY: [CallbackQueryHandler(got_teacher_clarification_handler, run_async=True)]
        },
        fallbacks=[
            MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True),
        ],
    )

    dispatcher.add_handler(conv_handler)
