import datetime as datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import bot.formats.decode as decode
import bot.ImportantDays as ImportantDays
from bot.schedule.week import get_current_week_number


def construct_teacher_workdays(
    week: int, schedule: list, room=None, group=None, day=None
):
    """
    Создает Inline клавиатуру с днями недели, когда у преподавателя есть пары.
    В случае если у преподавателя есть пары, то колбэк кнопки равен дню недели
    В случае если пар нет, то колбэк кнопки равен 'chill'
    @param week: Номер недели
    @param schedule: Расписание в JSON
    @param room: Название аудитории
    @param group: Название группы
    @param day: Номер дня недели
    @return: InlineKeyboard со стилизованными кнопками
    """
    if room:
        founded_days = list(
            {
                lesson["weekday"]
                for lesson in schedule
                if lesson["room"]["name"] == room and week in lesson["weeks"]
            }
        )

    elif group:
        founded_days = list(
            {
                lesson["weekday"]
                for lesson in schedule["lessons"]
                if week in lesson["weeks"]
            }
        )

    else:
        founded_days = list(
            {
                lesson["weekday"]
                for teacher in schedule
                for lesson in teacher["lessons"]
                if week in lesson["weeks"]
            }
        )

    weekdays = {
        1: "ПН",
        2: "ВТ",
        3: "СР",
        4: "ЧТ",
        5: "ПТ",
        6: "СБ",
    }

    button_rows = []
    row = []

    for i in range(1, 7):
        sign = ""
        sign1 = ""
        callback = i

        if i not in founded_days:
            sign = "⛔"
            callback = "chill"

        if day and i == day:
            sign = "◖"
            sign1 = "◗"

        row.append(
            InlineKeyboardButton(
                text=f"{sign}{weekdays[i]}{sign1 if sign1 else sign}",
                callback_data=callback,
            )
        )

        if len(row) == 3 or i == 6:
            button_rows.append(tuple(row))
            row = []

    if founded_days:
        button_rows.append(
            (InlineKeyboardButton(text="На неделю", callback_data="week"),)
        )

    button_rows.append((InlineKeyboardButton(text="Назад", callback_data="back"),))
    ready_markup = InlineKeyboardMarkup(button_rows)

    return ready_markup


def construct_teacher_markup(teachers):
    """
    Конструирует клавиатуру доступных преподавателей однофамильцев
    :param teachers: лист преподавателей
    """
    rawNames = teachers
    decoded_names = decode.decode_teachers(rawNames)

    btns = []

    for rawName, decoded_name in zip(rawNames, decoded_names):
        btns = btns + [[InlineKeyboardButton(decoded_name, callback_data=rawName)]]
    btns = btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)

    return TEACHER_CLARIFY_MARKUP


def construct_rooms_markup(rooms):
    """
    Конструирует клавиатуру доступных аудиторий
    :param rooms: лист аудиторий
    """
    btns = []

    for room in rooms:
        room_number, room_data, campus = room.split(":")
        room_text = f"{room_number} {campus}" if campus != "" else f"{room_number}"
        btns = btns + [[InlineKeyboardButton(room_text, callback_data=room_data)]]
    btns = btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    ROOM_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)

    return ROOM_CLARIFY_MARKUP


def construct_weeks_markup():
    """
    Создает KeyboardMarkup со списком недель, а также подставляет эмодзи
    если текущий день соответствует некоторой памятной дате+-интервал
    """
    current_week = get_current_week_number()
    week_indicator = "◖"
    week_indicator1 = "◗"
    today = datetime.date.today()

    for day in ImportantDays.important_days:
        if abs((day[ImportantDays.DATE] - today).days) <= day[ImportantDays.INTERVAL]:
            week_indicator = day[ImportantDays.SIGN]
            week_indicator1 = day[ImportantDays.SIGN]

    week_buttons = []
    row_buttons = []

    for i in range(1, 18):
        button_text = (
            f"{week_indicator}{i}{week_indicator1}" if i == current_week else str(i)
        )
        row_buttons.append(InlineKeyboardButton(text=button_text, callback_data=i))

        if len(row_buttons) == 4 or i == 17:
            week_buttons.append(tuple(row_buttons))
            row_buttons = []

    date_buttons = [
        [
            InlineKeyboardButton("Сегодня", callback_data="today"),
            InlineKeyboardButton("Завтра", callback_data="tomorrow"),
        ],
        [InlineKeyboardButton("Назад", callback_data="back")],
    ]

    reply_mark = InlineKeyboardMarkup(week_buttons + date_buttons)

    return reply_mark
