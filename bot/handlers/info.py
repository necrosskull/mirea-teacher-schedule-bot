from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Привествие бота при использовании команды /start
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет!\nЯ бот, который поможет вам найти "
        "расписание любого *преподавателя.*\n\nНапишите мне "
        "его фамилию, примеры:\n\n"
        "`Иванов`\n`Карпов Д.А.`\n\n"
        "Теперь доступен поиск по аудиториям и группам!\n"
        "Примеры:\n\n`И-202`\n`В-108`\n`И202а`\n\n"
        "Для поиска по группам напишите название группы, примеры:\n\n`ИВБО20`\n`КТСО-01-23`\n`ИКБО`\n\n"
        "Также вы можете использовать inline-режим, "
        "для этого в любом чате наберите *@mirea_teachers_bot* + *фамилию* и нажмите на кнопку с фамилией "
        "преподавателя.\n\n",
        parse_mode="Markdown",
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Информация о боте при использовании команды /about
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="*MIREA Teacher Schedule Bot*\n"
        "*Разработан* [necrosskull](https://github.com/necrosskull)\n\n"
        "*Исходный код: https://github.com/necrosskull/mirea-teacher-schedule-bot*",
        parse_mode="Markdown",
    )


def init_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("help", start))
