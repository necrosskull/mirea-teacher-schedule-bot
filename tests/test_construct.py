import datetime
from unittest.mock import patch

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fetch.models import (
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
from bot.handlers.construct import (
    construct_item_markup,
    construct_weeks_markup,
    construct_workdays,
)


def test_construct_item_markup():
    items = [
        SearchItem(type="teacher", uid=1, name="Карпов"),
        SearchItem(type="group", uid=2, name="ИКБО-20-23"),
    ]
    markup = construct_item_markup(items)
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 3
    assert markup.inline_keyboard[0][0].text == "Карпов"
    assert markup.inline_keyboard[0][0].callback_data == "teacher:1"
    assert markup.inline_keyboard[1][0].text == "ИКБО-20-23"
    assert markup.inline_keyboard[1][0].callback_data == "group:2"
    assert markup.inline_keyboard[2][0].text == "Назад"
    assert markup.inline_keyboard[2][0].callback_data == "back"


def test_construct_weeks_markup_normal_week():
    with patch("bot.handlers.construct.get_current_week_number", return_value=5):
        markup = construct_weeks_markup()
        assert isinstance(markup, InlineKeyboardMarkup)

        # Verify no empty button text
        for row in markup.inline_keyboard:
            for btn in row:
                assert btn.text != ""
                assert btn.callback_data != ""


def test_construct_weeks_markup_week_17():
    with patch("bot.handlers.construct.get_current_week_number", return_value=17):
        markup = construct_weeks_markup()
        all_callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row
        ]
        assert "18" in all_callbacks
        assert "19" in all_callbacks


def test_construct_weeks_markup_week_18():
    with patch("bot.handlers.construct.get_current_week_number", return_value=18):
        markup = construct_weeks_markup()
        # Verify no button has empty text
        for row in markup.inline_keyboard:
            for btn in row:
                assert btn.text != "", f"Found button with empty text: {btn}"
                assert btn.callback_data != ""


def test_construct_weeks_markup_week_20():
    with patch("bot.handlers.construct.get_current_week_number", return_value=20):
        markup = construct_weeks_markup()
        all_callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row
        ]
        assert "19" in all_callbacks
        assert "20" in all_callbacks
        assert "21" in all_callbacks


def test_construct_workdays():
    # Construct schedule with pairs only on Monday (2025-09-01)
    lesson = LessonSchedule(
        dates=["01-09-2025"],
        lesson_bells=LessonBells(number=1),
        subject="Пара",
    )
    schedule = ScheduleData(data=[lesson])

    with patch("bot.handlers.construct.get_dates_for_week") as mock_get_dates:
        mock_get_dates.return_value = [
            datetime.date(2025, 9, 1),
            datetime.date(2025, 9, 2),
            datetime.date(2025, 9, 3),
            datetime.date(2025, 9, 4),
            datetime.date(2025, 9, 5),
            datetime.date(2025, 9, 6),
        ]

        markup = construct_workdays(
            week=1,
            schedule=schedule,
            selected_date=datetime.date(2025, 9, 1),
        )

        # Monday has pair and is selected -> contains ◖ and ◗
        mon_btn = markup.inline_keyboard[0][0]
        assert "ПН" in mon_btn.text
        assert "◖" in mon_btn.text
        assert "◗" in mon_btn.text
        assert mon_btn.callback_data == "2025-09-01"

        # Tuesday has no pair -> marked with ⛔ and callback 'chill'
        tue_btn = markup.inline_keyboard[0][1]
        assert "⛔" in tue_btn.text
        assert tue_btn.callback_data == "chill"

        # Check 'На неделю' button is present because lesson_dates exist
        all_callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row
        ]
        assert "week" in all_callbacks
        assert "back" in all_callbacks
