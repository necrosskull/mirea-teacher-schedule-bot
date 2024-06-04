import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fetch.models import Lesson, ScheduleData, SearchItem
from bot.fetch.schedule import get_lessons
from bot.handlers import ImportantDays as ImportantDays
from bot.parse.semester import get_current_week_number, get_dates_for_week


def construct_item_markup(schedule_items: list[SearchItem]) -> InlineKeyboardMarkup:
    btns = []
    for item in schedule_items:
        callback = f"{item.type}:{item.uid}"
        btns = btns + [[InlineKeyboardButton(item.name, callback_data=callback)]]
    btns = btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)

    return TEACHER_CLARIFY_MARKUP


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

    week_constraint = 18

    for i in range(1, week_constraint):
        button_text = (
            f"{week_indicator}{i}{week_indicator1}" if i == current_week else str(i)
        )
        row_buttons.append(InlineKeyboardButton(text=button_text, callback_data=i))

        if len(row_buttons) == 4 or i == week_constraint - 1:
            week_buttons.append(tuple(row_buttons))
            row_buttons = []

    date_buttons = [
        [
            InlineKeyboardButton("Сегодня", callback_data="today"),
            InlineKeyboardButton("Завтра", callback_data="tomorrow"),
        ],
        [InlineKeyboardButton("Назад", callback_data="back")],
    ]

    if current_week >= 17:
        if current_week == 17:
            current_week_button = [
                [
                    InlineKeyboardButton("18", callback_data=18),
                    InlineKeyboardButton("19", callback_data=19),
                ]
            ]
        else:
            current_week_button = [
                [
                    InlineKeyboardButton(
                        f"{current_week - 1 if current_week > 18 else ''}",
                        callback_data=current_week - 1,
                    ),
                    InlineKeyboardButton(
                        f"◖{current_week}◗", callback_data=current_week
                    ),
                    InlineKeyboardButton(
                        f"{current_week + 1}", callback_data=current_week + 1
                    ),
                ]
            ]
    else:
        current_week_button = []

    reply_mark = InlineKeyboardMarkup(week_buttons + current_week_button + date_buttons)

    return reply_mark


def construct_workdays(week: int, schedule: ScheduleData, selected_date=None):
    weekdays = {
        1: "ПН",
        2: "ВТ",
        3: "СР",
        4: "ЧТ",
        5: "ПТ",
        6: "СБ",
    }

    dates = get_dates_for_week(week)
    lessons: list[Lesson] = get_lessons(schedule, dates)

    lesson_dates = [lesson.dates for lesson in lessons]

    button_rows = []
    row = []

    for i, date in enumerate(dates, start=1):
        sign = ""
        sign1 = ""
        callback = str(date)

        if (
            selected_date
            and date
            == datetime.datetime.strptime(str(selected_date), "%Y-%m-%d").date()
        ):
            sign = "◖"
            sign1 = "◗"

        if date not in lesson_dates:
            sign = "⛔"
            callback = "chill"

        row.append(
            InlineKeyboardButton(
                text=f"{sign}{weekdays[i]}{sign1 if sign1 else sign}",
                callback_data=callback,
            )
        )

        if len(row) == 3 or i == 6:
            button_rows.append(tuple(row))
            row = []

    if lesson_dates:
        button_rows.append(
            (InlineKeyboardButton(text="На неделю", callback_data="week"),)
        )

    button_rows.append((InlineKeyboardButton(text="Назад", callback_data="back"),))
    ready_markup = InlineKeyboardMarkup(button_rows)

    return ready_markup
