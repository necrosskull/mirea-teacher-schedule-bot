import requests
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from bot import ImportantDays
import datetime as datetime

from decode import decode_teachers


def construct_teacher_workdays(teacher: str, week: int, schedule: list):
    """
    Создает Inline клавиатуру с днями недели, когда у преподавателя есть пары.
    В случае если у преподавателя есть пары, то колбэк кнопки равен дню недели
    В случае если пар нет, то колбэк кнопки равен 'chill'
    @param teacher: Имя преподавателя
    @param week: Номер недели
    @param schedule: Расписание в JSON
    @return: InlineKeyboard со стилизованными кнопками
    """

    founded_days = list(
        {lesson['weekday'] for teacher in schedule for lesson in teacher['lessons'] if week in lesson['weeks']})

    no_work_indicator = "🏖️"
    weekdays = {
        1: "ПН",
        2: "ВТ",
        3: "СР",
        4: "ЧТ",
        5: "ПТ",
        6: "СБ",
    }
    ready_markup = InlineKeyboardMarkup([])
    row_list = []
    for i in range(1, 7):
        sign = ""
        callback = i

        if i not in founded_days:
            sign = "⛔"
            callback = "chill"
        row_list.append(
            InlineKeyboardButton(
                text=f"{sign}{weekdays[i]}{sign}",
                callback_data=callback))

        if i % 3 == 0:
            ready_markup.inline_keyboard.append(row_list)
            row_list = []

    if founded_days:  # добавляем кнопку "На неделю" только если есть пары на неделе
        row_list.append(
            InlineKeyboardButton(
                text="На неделю",
                callback_data="week"))
        ready_markup.inline_keyboard.append(row_list)
    row_list = []
    row_list.append(InlineKeyboardButton(text="Назад", callback_data="back"))
    ready_markup.inline_keyboard.append(row_list)

    return ready_markup


def construct_teacher_markup(teachers):
    """
    Конструирует клавиатуру доступных преподавателей однофамильцев
    :param teachers: лист преподавателей
    """
    rawNames = teachers
    decoded_names = decode_teachers(rawNames)

    btns = []

    for rawName, decoded_name in zip(rawNames, decoded_names):
        btns = btns + \
               [[InlineKeyboardButton(decoded_name, callback_data=rawName)]]
    btns = btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)

    return TEACHER_CLARIFY_MARKUP


def construct_weeks_markup():
    """
    Создает KeyboardMarkup со списком недель, а также подставляет эмодзи
    если текущий день соответствует некоторой памятной дате+-интервал
    """
    req = requests.get(
        "https://schedule.mirea.ninja/api/schedule/current_week").json()
    current_week = req["week"]
    week_indicator = "●"
    today = datetime.date.today()

    for day in ImportantDays.important_days:
        if abs((day[ImportantDays.DATE] -
                today).days) <= day[ImportantDays.INTERVAL]:
            week_indicator = day[ImportantDays.SIGN]

    reply_mark = InlineKeyboardMarkup([])
    button_list = []

    for i in range(1, 18):
        tmp_sign = ""
        if current_week == i:
            tmp_sign = week_indicator
        button_list.append(
            InlineKeyboardButton(
                text=f"{tmp_sign}{i}{tmp_sign}",
                callback_data=i))

        if i % 4 == 0 or i == 17:
            reply_mark.inline_keyboard.append(button_list)
            button_list = []

    backspace = []

    backspace.append(
        InlineKeyboardButton(
            text="Сегодня",
            callback_data="today"))

    backspace.append(
        InlineKeyboardButton(
            text="Завтра",
            callback_data="tomorrow"))

    reply_mark.inline_keyboard.append(backspace)

    backspace = []

    backspace.append(InlineKeyboardButton(text="Назад", callback_data="back"))
    reply_mark.inline_keyboard.append(backspace)

    return reply_mark
