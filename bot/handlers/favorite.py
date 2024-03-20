from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.db.database import add_favorite, get_user_favorites, insert_new_user

ASK_FAVOURITE = map(chr, range(3, 4))


async def save_favourite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Привествие бота при использовании команды /start
    """
    insert_new_user(update, context)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="ℹ️ Введите запрос для сохранения в избранное\n\nПример: `ИКБО-20-23`",
        parse_mode="Markdown",
    )
    return ASK_FAVOURITE


async def ask_favourite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_favorite(update, context)
    query = get_user_favorites(update, context)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ Успешно добавлено: {query}\n\nЧтобы посмотреть сохраненное расписание, используйте команду /fav",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


def init_handlers(application: Application):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("save", save_favourite, block=False)],
        states={
            ASK_FAVOURITE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, ask_favourite, block=False
                )
            ],
        },
        fallbacks=[CommandHandler("save", save_favourite, block=False)],
    )
    application.add_handler(conv_handler)
