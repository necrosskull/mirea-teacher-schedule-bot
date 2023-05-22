from telegram import Update
from telegram.ext import CallbackContext

import bot.formats.decode as decode
import bot.formats.formatting as formatting
import bot.handlers.construct as construct
import bot.handlers.fetch as fetch

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, BACK = range(5)


def send_week_selector(
        update: Update,
        context: CallbackContext,
        firsttime=False):
    """
    Отправка селектора недели. По умолчанию изменяет предыдущее сообщение, но при firsttime=True отправляет в виде
    нового сообщения @param update: Update class of API @param context: CallbackContext of API @param firsttime:
    Впервые ли производится общение с пользователем @return: Статус следующего шага - GETWEEK
    """
    teacher = ", ".join(decode.decode_teachers([context.user_data["teacher"]]))

    if firsttime:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct.construct_weeks_markup()
        )

    else:
        update.callback_query.edit_message_text(
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct.construct_weeks_markup()
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
    few_teachers_markup = construct.construct_teacher_markup(available_teachers)

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
    teacher = ", ".join(decode.decode_teachers([context.user_data["teacher"]]))
    week = context.user_data["week"]
    schedule = context.user_data["schedule"]
    teacher_workdays = construct.construct_teacher_workdays(teacher, week, schedule)

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

    parsed_schedule = formatting.parse(
        schedule_data,
        weekday,
        week,
        teacher_surname,
        context)

    parsed_schedule = formatting.remove_duplicates_merge_groups_with_same_lesson(
        parsed_schedule)

    parsed_schedule = formatting.merge_weeks_numbers(parsed_schedule)

    if len(parsed_schedule) == 0:
        update.callback_query.answer(
            text="В этот день пар нет.", show_alert=True)
        return GETWEEK

    blocks_of_text = formatting.format_outputs(parsed_schedule, context)

    return telegram_delivery_optimisation(blocks_of_text, update, context)


def telegram_delivery_optimisation(
        blocks: list,
        update: Update,
        context: CallbackContext):
    teacher = context.user_data["teacher"]

    context.user_data["schedule"] = fetch.fetch_schedule_by_name(
        context.user_data["teacher"])

    schedule = context.user_data["schedule"]
    week = context.user_data["week"]
    teacher_workdays = construct.construct_teacher_workdays(teacher, week, schedule)

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
