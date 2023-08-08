from telegram import Update
from telegram.ext import CallbackContext, CommandHandler


async def start(update: Update, context: CallbackContext):
    """
    Привествие бота при использовании команды /start
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет!\nЯ бот, который поможет вам найти "
             "расписание любого *преподавателя.*\nНапишите мне "
             "его фамилию "
             "в формате:\n*Иванов* или *Иванов И.И.*\n\n"
             "Теперь доступен поиск по аудиториям!\n"
             "Для этого напишите слово `ауд` и номер аудитории, примеры:\n\n`ауд И-202`\n`ауд В-108`\n`ауд И-202-а`\n\n"
             "Также вы можете использовать inline-режим, "
             "для этого в любом чате наберите *@mirea_teachers_bot* + *фамилию* и нажмите на кнопку с фамилией "
             "преподавателя.\n\n"
             "Возникла проблема? Обратитесь в поддержу *@mirea_help_bot*!",
        parse_mode="Markdown")


async def about(update: Update, context: CallbackContext):
    """
    Информация о боте при использовании команды /about
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="*MIREA Teacher Schedule Bot*\n"
             "*Разработан Mirea Ninja*\n\n"
             "*Исходный код: https://github.com/mirea-ninja/mirea-teacher-schedule-bot*",
        parse_mode="Markdown")


def init_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("help", start))
