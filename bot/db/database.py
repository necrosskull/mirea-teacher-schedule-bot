from bot.db.sqlite import ScheduleBot, db


def insert_new_user(update, context):
    """
    Добавление нового пользователя в базу данных
    @param update: Обновление
    @param context: Контекст
    @return: None
    """
    user = update.effective_user
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

    db.close()
