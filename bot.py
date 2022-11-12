import logging
import config
import requests
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          Filters, MessageHandler, Updater)

TELEGRAM_TOKEN = config.token

updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

GETNAME, GETDAY, GETWEEK = range(3)

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


def fetch_schedule_by_name(teacher_name):
    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher_name}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None


def start(update: Update, context: CallbackContext) -> int:
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Введите фамилию преподавателя"
    )

    # Переключаемся в состояние GETNAME (ожидание ввода фамилии)
    return GETNAME


def get_name(update: Update, context: CallbackContext) -> int:
    teacher = update.message.text

    if len(teacher) < 4:
        update.message.reply_text("Фамилия должна быть больше 3 символов")
        return GETNAME

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

    # Отправляем клавиатуру с выбором дня недели
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введите день недели",
        reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
    )

    # Устанавливаем состояние в GETDAY (ожидание ввода дня недели)
    return GETDAY


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
    if not teacher_schedule:
        update.message.reply_text(
            "В этот день нет пар", reply_markup=ReplyKeyboardRemove()
        )
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите день недели",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
        )
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
    text_len = len(text)

    for i in range(0, text_len, 4096):
        update.message.reply_text(text[i: i + 4096], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True),
        ],
        states={
            GETNAME: [MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True)],
            GETDAY: [MessageHandler(Filters.text, get_day, run_async=True)],
            GETWEEK: [MessageHandler(Filters.text, get_week, run_async=True)],
        },
        fallbacks=[MessageHandler(Filters.text, start, run_async=True)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()


if __name__ == "__main__":
    main()
