import json

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import CallbackContext, InlineQueryHandler, ChosenInlineResultHandler, CallbackQueryHandler

from bot.InlineStep import EInlineStep
from bot.construct import construct_weeks_markup
from bot.decode import decode_teachers
from bot.handlers import fetch_schedule_by_name, got_week_handler, got_day_handler, GETDAY, BACK, GETWEEK
from bot.lazy_logger import lazy_logger
from bot.parse import check_same_surnames


def inlinequery(update: Update, context: CallbackContext):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """
    query = update.inline_query.query

    if not query:
        return

    if len(query) < 3:
        return

    lazy_logger.info(json.dumps(
        {"type": "query",
         "queryId": update.inline_query.id,
         "query": query.lower(),
         **update.inline_query.from_user.to_dict()}, ensure_ascii=False))

    query = query.title()

    if " " not in query:
        query += " "

    teacher_schedule = fetch_schedule_by_name(query)

    if teacher_schedule is None:
        return

    surnames = check_same_surnames(teacher_schedule, query)

    if len(surnames) == 0:
        return

    inline_results = []

    decoded_surnames = decode_teachers(surnames)
    userid = str(update.inline_query.from_user.id)

    for surname, decoded_surname in zip(surnames, decoded_surnames):
        inline_results.append(InlineQueryResultArticle(
            id=surname,
            title=decoded_surname,
            description="Нажми, чтобы посмотреть расписание",
            input_message_content=InputTextMessageContent(
                message_text=f"Выбран преподаватель: {decoded_surname}!"
            ),
            reply_markup=construct_weeks_markup(),

        ))

    update.inline_query.answer(inline_results, cache_time=10, is_personal=True)


def answer_inline_handler(update: Update, context: CallbackContext):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if update.chosen_inline_result is not None:
        context.user_data["teacher"] = update.chosen_inline_result.result_id
        context.user_data["inline_step"] = EInlineStep.ask_week
        context.user_data["inline_message_id"] = update.chosen_inline_result.inline_message_id
        return


def inline_dispatcher(update: Update, context: CallbackContext):
    """
    Обработка вызовов в чатах на основании Callback вызова
    """
    if "inline_step" not in context.user_data:
        deny_inline_usage(update)
        return

    # Если Id сообщения в котором мы нажимаем на кнопки не совпадает с тем, что было сохранено в контексте при вызове
    # меню, то отказываем в обработке

    if update.callback_query.inline_message_id and update.callback_query.inline_message_id != \
            context.user_data["inline_message_id"]:
        deny_inline_usage(update)
        return

    status = context.user_data["inline_step"]
    if status == EInlineStep.completed or status == EInlineStep.ask_teacher:
        deny_inline_usage(update)
        return

    if status == EInlineStep.ask_week:
        context.user_data['available_teachers'] = None
        context.user_data["schedule"] = fetch_schedule_by_name(
            context.user_data["teacher"])

        target = got_week_handler(update, context)

        if target == GETDAY:
            context.user_data["inline_step"] = EInlineStep.ask_day

        elif target == BACK:
            context.user_data["inline_step"] = EInlineStep.ask_day

    if status == EInlineStep.ask_day:
        target = got_day_handler(update, context)
        if target == GETWEEK:
            context.user_data["schedule"] = fetch_schedule_by_name(
                context.user_data["teacher"])
            context.user_data["inline_step"] = EInlineStep.ask_week

        elif target == BACK:
            context.user_data["inline_step"] = EInlineStep.ask_day
        return


def deny_inline_usage(update: Update):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    update.callback_query.answer(
        text="Вы не можете использовать это меню, т.к. оно не относится к вашему запросу",
        show_alert=True)
    return


def init_handlers(dispatcher):
    dispatcher.add_handler(InlineQueryHandler(inlinequery, run_async=True))
    dispatcher.add_handler(ChosenInlineResultHandler(answer_inline_handler, run_async=True))
    dispatcher.add_handler(CallbackQueryHandler(inline_dispatcher, run_async=True))
