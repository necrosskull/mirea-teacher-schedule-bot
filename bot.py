import datetime
import logging
import sqlite3

import requests
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

import config

conn = sqlite3.connect("teachers_schedule_bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute(
    """CREATE TABLE IF NOT EXISTS user_settings(
   userid INT PRIMARY KEY,
   settings TEXT);
"""
)

TELEGRAM_TOKEN = config.token

updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

GETSETTINGS, GETNAME, GETDAY, GETWEEK, GETDATE, CONFIGURE = range(6)

WEEKDAYS = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
}

WEEKDAYS_KEYBOARD_MARKUP = ReplyKeyboardMarkup(
    [
        ["Понедельник", "Вторник"],
        ["Среда", "Четверг"],
        ["Пятница", "Суббота"],
        ["Назад"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

WEEKS_KEYBOARD_MARKUP = ReplyKeyboardMarkup(
    [
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
        ["9", "10", "11", "12"],
        ["13", "14", "15", "16", "17"],
        ["Назад"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

SETTINGS_MARKUP = ReplyKeyboardMarkup(
    [
        ["Дата в формате dd.mm", "Неделя с выбором дня"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

SETTINGS_COMMAND = ReplyKeyboardMarkup(
    [
        ["Настройки выбора даты"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def settings_command(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Выберите параметр для изменения",
        reply_markup=SETTINGS_COMMAND,
    )
    return CONFIGURE
def configure(update: Update, context: CallbackContext) -> int:
    if update.message.text == "Настройки выбора даты":
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите метод, по которому будет осуществляться поиск",
            reply_markup=SETTINGS_MARKUP,
        )
    return GETSETTINGS



def settings_choice(update: Update):
    settings_choice_message = update.message.text

    if settings_choice_message == "Настойки выбора даты":
        update.message.reply_text(
            "Выберите метод, по которому будет осуществляться поиск",
            reply_markup=SETTINGS_MARKUP,
        )
        settings_configure(update)

    return GETSETTINGS

def fetch_schedule_by_name(teacher_name):
    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher_name}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None


def start(update: Update, context: CallbackContext) -> int:
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Выберите метод, по которому будет осуществляться поиск",
        reply_markup=SETTINGS_MARKUP,
    )

    # Переключаемся в состояние GETSETTINGS (ожидание ввода настроек)
    return GETSETTINGS


def settings_configure(update: Update, context: CallbackContext):
    settings = update.message.text

    if settings == "Дата в формате dd.mm":
        context.user_data["settings"] = "date"
    elif settings == "Неделя с выбором дня":
        context.user_data["settings"] = "week"
    else:
        return GETSETTINGS

    add_settings(update.message.from_user.id, context.user_data["settings"])

    if context.user_data["settings"] == "date":
        update.message.reply_text(
            "Введите дату в формате dd.mm",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GETDATE

    elif context.user_data["settings"] == "week":
        update.message.reply_text(
            "Введите фамилию преподавателя",

        )
        return GETNAME

    else:
        update.message.reply_text(
            "Выберите метод, по которому будет осуществляться поиск",
            reply_markup=SETTINGS_MARKUP,
        )
        return GETSETTINGS


def add_settings(user_id: int, settings_type: str) -> None:
    cur.execute(
        "INSERT OR REPLACE INTO user_settings(userid, settings) VALUES (?, ?)",
        (
            user_id,
            settings_type,
        ),
    )
    conn.commit()


def get_name(update: Update, context: CallbackContext) -> int:
    teacher = update.message.text + " "

    teacher_schedule = fetch_schedule_by_name(teacher)

    if teacher_schedule is None:
        update.message.reply_text("Преподаватель не найден\nПопробуйте еще раз")
        return GETNAME

    # Устанавливаем фамилию преподавателя в контексте.
    # `user_data` - это словарь, который можно использовать для хранения любых данных.
    # Для каждого обновления от одного и того же пользователя он будет одинаковым.
    context.user_data["teacher"] = teacher

    # Устанавливаем расписание преподавателя в контексте для избежания повторных запросов
    context.user_data["teacher_schedule"] = teacher_schedule

    user_id = update.effective_chat.id
    cur.execute("SELECT settings FROM user_settings WHERE userid = ?", (user_id,))
    settings = cur.fetchone()[0]

    if settings == "date":
        if "week" not in context.user_data or "weekday" not in context.user_data:
            update.message.reply_text(
                "Введите дату в формате dd.mm",
                reply_markup=ReplyKeyboardRemove(),
            )
            return GETDATE
        else:
            week = context.user_data["week"]
            weekday = context.user_data["weekday"]

            parsed_schedule = parse(teacher_schedule, weekday, week)
            parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(
                parsed_schedule
            )
            parsed_schedule = merge_weeks_numbers(parsed_schedule)

            is_having_schedule = have_teacher_lessons(parsed_schedule, update, context)

            if not is_having_schedule:
                return GETDATE

            text = format_outputs(parsed_schedule)

            return for_telegram(text, update)

    elif settings == "week" or settings is None:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите день недели",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
        )
        return GETDAY


def get_week_and_weekday(date: datetime.date):
    """Функция взята из
    https://github.com/mirea-ninja/rtu-mirea-schedule/blob/287773afdd7f6a04f8349efee950fc154fcbeef7/app/core/schedule_utils.py#L7
    """
    now = date
    start_date = datetime.date(date.year, 9, 1)

    if now < start_date:
        return 1, now.isoweekday()

    week = now.isocalendar()[1] - start_date.isocalendar()[1]

    if now.isocalendar()[2] != 0:
        week += 1

    return week, now.isoweekday()


def get_date(update: Update, context: CallbackContext):
    date = update.message.text

    try:
        date = datetime.datetime.strptime(date, "%d.%m")
        date = datetime.date(datetime.datetime.now().year, date.month, date.day)
    except ValueError:
        update.message.reply_text(
            "Неверный формат даты. Дата должна быть в формате dd.mm"
        )
        return GETDATE

    context.user_data["date"] = date

    week, weekday = get_week_and_weekday(date)

    context.user_data["week"] = week
    context.user_data["weekday"] = weekday

    week = context.user_data["week"]
    weekday = context.user_data["weekday"]

    parsed_schedule = parse(context.user_data["teacher_schedule"], weekday, week)
    parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(
        parsed_schedule
    )
    parsed_schedule = merge_weeks_numbers(parsed_schedule)

    is_having_schedule = have_teacher_lessons(parsed_schedule, update, context)

    if not is_having_schedule:
        return GETDATE

    text = format_outputs(parsed_schedule)

    return for_telegram(text, update)


def get_day(update: Update, context: CallbackContext):
    day = update.message.text.lower()

    for key, value in WEEKDAYS.items():
        if day == value.lower():
            # Устанавливаем день недели в контексте
            context.user_data["day"] = key

            # Отправляем клавиатуру с выбором номера недели
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Выберите неделю",
                reply_markup=WEEKS_KEYBOARD_MARKUP,
            )

            # Устанавливаем состояние в GETWEEK (ожидание ввода номера недели)
            return GETWEEK

    if day == "назад":
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите фамилию преподавателя",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GETNAME
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Неверный ввод",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GETDAY


def get_week(update: Update, context: CallbackContext):
    week_number = update.message.text.lower()

    if week_number == "назад":
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите день недели",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
        )
        return GETDAY

    if not week_number.strip().isdigit():
        update.message.reply_text("Неверный ввод", reply_markup=ReplyKeyboardRemove())
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите неделю",
            reply_markup=WEEKS_KEYBOARD_MARKUP,
        )
        return GETWEEK

    week_number = int(week_number)
    weekday = context.user_data["day"]
    schedule_data = context.user_data["teacher_schedule"]

    parsed_schedule = parse(schedule_data, weekday, week_number)
    parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(parsed_schedule)
    parsed_schedule = merge_weeks_numbers(parsed_schedule)

    is_having_schedule = have_teacher_lessons(parsed_schedule, update, context)

    if not is_having_schedule:
        return GETDAY

    # Отправляем расписание преподавателя
    text = format_outputs(parsed_schedule)

    return for_telegram(text, update)


def parse(teacher_schedule, weekday, week_number):
    teacher_schedule = teacher_schedule["schedules"]
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["weekday"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["group"])
    teacher_schedule = list(
        filter(lambda x: x["weekday"] == int(weekday), teacher_schedule)
    )
    teacher_schedule = list(
        filter(lambda x: int(week_number) in x["lesson"]["weeks"], teacher_schedule)
    )
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_start"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_end"])

    return teacher_schedule


def remove_duplicates_merge_groups_with_same_lesson(teacher_schedule):
    remove_index = []
    for i in range(len(teacher_schedule)):
        for j in range(i + 1, len(teacher_schedule)):
            if (
                    teacher_schedule[i]["weekday"] == teacher_schedule[j]["weekday"]
                    and teacher_schedule[i]["lesson"]["name"]
                    == teacher_schedule[j]["lesson"]["name"]
                    and teacher_schedule[i]["lesson"]["weeks"]
                    == teacher_schedule[j]["lesson"]["weeks"]
                    and teacher_schedule[i]["lesson"]["time_start"]
                    == teacher_schedule[j]["lesson"]["time_start"]
            ):
                teacher_schedule[i]["group"] += ", " + teacher_schedule[j]["group"]
                remove_index.append(j)

    remove_index = set(remove_index)
    for i in sorted(remove_index, reverse=True):
        del teacher_schedule[i]
    return teacher_schedule


def have_teacher_lessons(teacher_schedule, update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    cur.execute("SELECT settings FROM user_settings WHERE userid = ?", (user_id,))
    settings = cur.fetchone()[0]

    if not teacher_schedule:
        update.message.reply_text(
            "В этот день нет пар", reply_markup=ReplyKeyboardRemove()
        )

        if context.user_data["settings"] == "date":
            update.message.reply_text(
                "Введите дату в формате dd.mm",
                reply_markup=ReplyKeyboardRemove(),
            )
            return GETDATE

        elif context.user_data["settings"] == "week":
            update.message.reply_text(
                "Введите номер недели",
                reply_markup=WEEKS_KEYBOARD_MARKUP,
            )
            return GETWEEK
        return False
    return True


def merge_weeks_numbers(teacher_schedule):
    for i in range(len(teacher_schedule)):
        weeks = teacher_schedule[i]["lesson"]["weeks"]
        if weeks == list(range(1, 18)):
            weeks = "все"
        elif weeks == list(range(2, 18, 2)):
            weeks = "по чётным"
        elif weeks == list(range(1, 18, 2)):
            weeks = "по нечётным"
        else:
            weeks = ", ".join(str(week) for week in weeks)
        teacher_schedule[i]["lesson"]["weeks"] = weeks
    return teacher_schedule


def format_outputs(schedules):
    text = ""

    for schedule in schedules:
        room = ", ".join(schedule["lesson"]["rooms"])
        teachers = ", ".join(schedule["lesson"]["teachers"])
        weekday = WEEKDAYS[schedule["weekday"]]

        text += f'📝 Пара № {schedule["lesson_number"] + 1} в ⏰ {schedule["lesson"]["time_start"]}–{schedule["lesson"]["time_end"]}\n'
        text += f'📝 {schedule["lesson"]["name"]}\n'
        text += f'👥 Группы: {schedule["group"]}\n'
        text += f'📚 Тип: {schedule["lesson"]["types"]}\n'
        text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
        text += f"🏫 Аудитории: {room}\n"
        text += f'📅 Недели: {schedule["lesson"]["weeks"]}\n'
        text += f"📆 День недели: {weekday}\n\n"

    return text


def for_telegram(text, update: Update):
    """Функция для отправки сообщения блоками по 8 строк. Необходимо, чтобы избежать ошибки отправки большого
    сообщения"""
    text_len = len(text)

    for i in range(0, text_len, 4096):
        update.message.reply_text(
            text[i: i + 4096], reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END


def main():
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start, run_async=True),
            CommandHandler("settings", settings_command, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True),
        ],
        states={
            GETSETTINGS: [
                MessageHandler(
                    Filters.text & ~Filters.command, settings_configure, run_async=True
                )
            ],
            CONFIGURE: [MessageHandler(Filters.text & ~Filters.command, configure, run_async=True)],
            GETDATE: [MessageHandler(Filters.text & ~Filters.command, get_date, run_async=True)],
            GETNAME: [
                MessageHandler(
                    Filters.text & ~Filters.command, get_name, run_async=True
                )
            ],
            GETDAY: [
                MessageHandler(Filters.text & ~Filters.command, get_day, run_async=True)
            ],
            GETWEEK: [
                MessageHandler(
                    Filters.text & ~Filters.command, get_week, run_async=True
                )
            ],
        },
        fallbacks=[MessageHandler(Filters.text, start, run_async=True)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()


if __name__ == "__main__":
    main()
