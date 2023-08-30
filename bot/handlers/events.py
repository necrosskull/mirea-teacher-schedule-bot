from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from bot import config


async def toggle_maintenance_mode(update: Update, context: CallbackContext):
    """Toggle maintenance mode"""

    if update.message.from_user.id not in config.ADMINS:
        return

    if context.bot_data["maintenance_mode"]:
        context.bot_data["maintenance_mode"] = False
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Режим обслуживания отключен",
        )
    else:
        context.bot_data["maintenance_mode"] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Режим обслуживания включен",
        )


def init_handlers(application):
    application.add_handler(CommandHandler("work", toggle_maintenance_mode))
