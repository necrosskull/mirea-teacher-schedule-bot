import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fetch.models import Lesson, ScheduleData, SearchItem
from bot.fetch.schedule import get_lessons
from bot.handlers import ImportantDays as ImportantDays
from bot.parse.semester import get_current_week_number, get_dates_for_week


def construct_item_markup(schedule_items: list[SearchItem]) -> InlineKeyboardMarkup:
    btns: list[list[InlineKeyboardButton]] = []
    for item in schedule_items:
        callback = f"{item.type}:{item.uid}"
        btns.append([InlineKeyboardButton(text=item.name, callback_data=callback)])
    btns.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(inline_keyboard=btns)

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
    for day in ImportantDays.get_important_days(today.year):
        if abs((day[ImportantDays.DATE] - today).days) <= day[ImportantDays.INTERVAL]:
            week_indicator = day[ImportantDays.SIGN]
            week_indicator1 = day[ImportantDays.SIGN]

    week_buttons: list[list[InlineKeyboardButton]] = []
    row_buttons: list[InlineKeyboardButton] = []

    week_constraint = 18

    for i in range(1, week_constraint):
        button_text = (
            f"{week_indicator}{i}{week_indicator1}" if i == current_week else str(i)
        )
        row_buttons.append(
            InlineKeyboardButton(text=button_text, callback_data=str(i))
        )

        if len(row_buttons) == 4 or i == week_constraint - 1:
            week_buttons.append(row_buttons)
            row_buttons = []

    date_buttons = [
        [
            InlineKeyboardButton(text="Сегодня", callback_data="today"),
            InlineKeyboardButton(text="Завтра", callback_data="tomorrow"),
        ],
        [InlineKeyboardButton(text="Назад", callback_data="back")],
    ]

    if current_week >= 17:
        if current_week == 17:
            current_week_button = [
                [
                    InlineKeyboardButton(text="18", callback_data="18"),
                    InlineKeyboardButton(text="19", callback_data="19"),
                ]
            ]
        else:
            row = []
            if current_week > 18:
                row.append(
                    InlineKeyboardButton(
                        text=str(current_week - 1),
                        callback_data=str(current_week - 1),
                    )
                )
            row.append(
                InlineKeyboardButton(
                    text=f"◖{current_week}◗", callback_data=str(current_week)
                )
            )
            row.append(
                InlineKeyboardButton(
                    text=str(current_week + 1), callback_data=str(current_week + 1)
                )
            )
            current_week_button = [row]
    else:
        current_week_button = []

    reply_mark = InlineKeyboardMarkup(
        inline_keyboard=week_buttons + current_week_button + date_buttons
    )

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

    button_rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    selected_d = None
    if selected_date:
        try:
            selected_d = (
                selected_date
                if isinstance(selected_date, datetime.date)
                else datetime.datetime.strptime(str(selected_date), "%Y-%m-%d").date()
            )
        except (ValueError, TypeError):
            selected_d = None

    for i, date in enumerate(dates, start=1):
        sign = ""
        sign1 = ""
        callback = str(date)

        if selected_d and date == selected_d:
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
            button_rows.append(row)
            row = []

    if lesson_dates:
        button_rows.append([InlineKeyboardButton(text="На неделю", callback_data="week")])

    button_rows.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    ready_markup = InlineKeyboardMarkup(inline_keyboard=button_rows)

    return ready_markup
