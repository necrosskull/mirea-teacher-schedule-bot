from telegram import Update, parsemode
from telegram.ext import CallbackContext, CommandHandler


def start(update: Update, context: CallbackContext):
    """
    Привествие бота при использовании команды /start
    """
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет!\nЯ бот, который поможет вам найти "
             "расписание любого *преподавателя.*\nНапишите мне "
             "его фамилию "
             "в формате:\n*Иванов* или *Иванов И.И.*\n\n"
             "Также вы можете использовать inline-режим, "
             "для этого в любом чате наберите *@mirea_teachers_bot* + *фамилию* и нажмите на кнопку с фамилией "
             "преподавателя.\n\n"
             "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
        parse_mode="Markdown")


def about(update: Update, context: CallbackContext):
    """
    Информация о боте при использовании команды /about
    """
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="*MIREA Teacher Schedule Bot*\n"
        "*Разработан Mirea Ninja*\n\n"
        "*Исходный код: https://github.com/mirea-ninja/mirea-teacher-schedule-bot*",
        parse_mode="Markdown")


def init_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("about", about))
    dispatcher.add_handler(CommandHandler("help", start))
