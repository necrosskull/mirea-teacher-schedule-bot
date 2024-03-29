from telegram import Update
from telegram.ext import ContextTypes

from bot.db.sqlite import ScheduleBot, db


def insert_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Добавление нового пользователя в базу данных
    @param update: Обновление
    @param context: Контекст
    @return: None
    """
    user = update.effective_user
    try:
        db.connect()

        usr, created = ScheduleBot.get_or_create(
            id=user.id,
            defaults={
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )

        if not created:
            usr.username = user.username
            usr.first_name = user.first_name
            usr.last_name = user.last_name
            usr.save()

    except Exception:
        pass
    finally:
        db.close()


def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db.connect()
        user = ScheduleBot.get_by_id(update.effective_user.id)
        user.favorite = update.message.text
        user.save()
    except Exception:
        pass
    finally:
        db.close()


def get_user_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db.connect()
        user = ScheduleBot.get_or_none(
            ScheduleBot.id == update.effective_user.id,
            ScheduleBot.favorite.is_null(False),
        )

        if user:
            favorites = user.favorite
            return favorites
        else:
            return None
    except Exception:
        return None
    finally:
        db.close()
