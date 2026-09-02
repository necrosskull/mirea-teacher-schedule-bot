from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
@router.message(Command("help"))
async def start(message: Message):
    """
    Привествие бота при использовании команды /start
    """
    await message.answer(
        text="Привет!\nЯ бот, который поможет вам найти "
        "расписание любого *преподавателя* и не только!\n\n"
        "Для получения расписания напишите:\n\n"
        "👥 Номер группы (например, `ИКБО-20-23`)\n"
        "🧑‍🏫 Фамилию преподавателя (например, `Карпов Д.А.`)\n"
        "🏫 Номер аудитории (например, `Г-212`)\n\n"
        "Для сохранения расписания в избранное используйте команду /save.\n\n"
        "Для уведомлений о расписании на завтра:\n"
        "• /notify — включить рассылку и выбрать время\n"
        "• /notifyoff — отключить рассылку\n\n"
        "Также вы можете использовать inline-режим, "
        "для этого в любом чате наберите *@mirea_teachers_bot* + *фамилию* и нажмите на кнопку с фамилией "
        "преподавателя.\n\n",
    )


@router.message(Command("about"))
async def about(message: Message):
    """
    Информация о боте при использовании команды /about
    """
    await message.answer(
        text="*MIREA Teacher Schedule Bot*\n"
        "*Разработан* [necrosskull](https://github.com/necrosskull)\n\n"
        "*Исходный код: https://github.com/necrosskull/mirea-teacher-schedule-bot*",
    )


@router.message(Command("app"))
async def open_app(message: Message):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from bot.config import settings

    webapp_url = settings.webapp_url or f"http://localhost:{settings.webapp_port}/app"

    keyboard = None
    if settings.webapp_url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📱 Открыть расписание",
                        web_app=WebAppInfo(url=settings.webapp_url),
                    )
                ]
            ]
        )

    await message.answer(
        text="📱 *Интерактивное Mini App расписание!*\n\n"
        "✨ Мгновенный показ вашего избранного (FAV)\n"
        "👆 Листание дней недели свайпами\n"
        "🟢 Индикатор текущей пары в реальном времени\n"
        "🔍 Удобный поиск групп, преподавателей и аудиторий\n\n"
        + (f"Ссылка для браузера: {webapp_url}" if not settings.webapp_url else ""),
        reply_markup=keyboard,
    )



def init_handlers(dispatcher):
    dispatcher.include_router(router)
