import asyncio
import time

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from bot.db.sqlite import ScheduleBot, db
import bot.lazy_logger as logger
from bot import config


async def toggle_maintenance_mode(update: Update, context: CallbackContext):
    """Toggle maintenance mode"""

    if update.message.from_user.id not in config.ADMINS:
        return

    maintenance_message = " ".join(context.args) if context.args else None
    context.bot_data["maintenance_message"] = maintenance_message

    if context.bot_data["maintenance_mode"]:
        context.bot_data["maintenance_mode"] = False
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Режим обслуживания отключен",
        )
    else:
        context.bot_data["maintenance_mode"] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ Режим обслуживания включен",
        )


async def send_message_to_all_users(update: Update, context: CallbackContext):
    """Send message to all users"""

    if update.message.from_user.id not in config.ADMINS:
        return

    if not context.args:
        return

    message = update.message.text[6:]

    db.connect()

    users = ScheduleBot.select()
    user_ids = [user.id for user in users]

    db.close()

    for user in user_ids:
        await asyncio.sleep(0.5)
        try:
            await context.bot.send_message(
                chat_id=user,
                text=message,
                parse_mode="Markdown"
            )
            logger.lazy_logger.info(f"Message sent to {user}")
        except Exception as e:
            logger.lazy_logger.info(f"Error sending message to {user}: {e}")


def init_handlers(application):
    application.add_handler(CommandHandler("work", toggle_maintenance_mode, block=False))
    application.add_handler(CommandHandler("send", send_message_to_all_users, block=False))
