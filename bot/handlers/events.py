import asyncio
import re

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka.integrations.aiogram import FromDishka, inject

import bot.logs.lazy_logger as logger
from bot.config import settings
from bot.handlers.context import bot_data
from bot.service import UserService

router = Router()
SEND_LINK_PATTERN = re.compile(r"\[\[([^\]|]{1,64})\|(https?://\S+)\]\]\s*$")


def _is_admin(message: Message) -> bool:
    return message.from_user.id in settings.admins


def _extract_inline_link(text: str) -> tuple[str, InlineKeyboardMarkup | None]:
    match = SEND_LINK_PATTERN.search(text)
    if not match:
        return text, None

    button_text = match.group(1).strip()
    button_url = match.group(2).strip()

    if not button_text:
        return text, None

    cleaned_text = text[: match.start()].rstrip()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]]
    )
    return cleaned_text, markup


@router.message(Command("work"))
async def toggle_maintenance_mode(message: Message):
    """Toggle maintenance mode"""

    if not _is_admin(message):
        return

    command_parts = message.text.split(maxsplit=1)
    maintenance_message = command_parts[1] if len(command_parts) > 1 else None
    bot_data["maintenance_message"] = maintenance_message

    if bot_data["maintenance_mode"]:
        bot_data["maintenance_mode"] = False
        await message.answer(text="❌ Режим обслуживания отключен")
    else:
        bot_data["maintenance_mode"] = True
        await message.answer(text="✅ Режим обслуживания включен")


@router.message(Command("send"))
@inject
async def send_message_to_all_users(
    message: Message,
    user_service: FromDishka[UserService],
):
    """Send message to all users"""

    if not _is_admin(message):
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        return

    text_to_send, reply_markup = _extract_inline_link(command_parts[1])
    user_ids = await user_service.get_all_user_ids()

    for user in user_ids:
        await asyncio.sleep(0.5)
        try:
            await message.bot.send_message(
                chat_id=user,
                text=text_to_send,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            logger.lazy_logger.logger.info(f"Message sent to {user}")
        except Exception as e:
            logger.lazy_logger.logger.info(f"Error sending message to {user}: {e}")
            await user_service.delete_user(user)


@router.message(Command("stats"))
@inject
async def stats(
    message: Message,
    user_service: FromDishka[UserService],
):
    if not _is_admin(message):
        return

    all_users = await user_service.count_all_users()
    with_favorite = await user_service.count_users_with_favorite()
    with_notifications = await user_service.count_users_with_notifications()

    await message.answer(
        "📊 Статистика пользователей:\n"
        f"👥 Всего пользователей: {all_users}\n"
        f"⭐ С избранным расписанием: {with_favorite}\n"
        f"🔔 С включенными напоминаниями: {with_notifications}"
    )


def init_handlers(dispatcher):
    dispatcher.include_router(router)
