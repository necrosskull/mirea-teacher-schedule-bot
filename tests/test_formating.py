from datetime import date
from unittest.mock import MagicMock

from bot.fetch.models import (
    Campus,
    Classroom,
    Lesson,
    LessonBells,
    SearchItem,
    Teacher,
)
from bot.parse.formating import format_outputs


def make_lesson(
    subject="Математический анализ",
    lesson_type="lecture",
    number=1,
    start_time="09:00",
    end_time="10:30",
    dates=date(2025, 9, 1),  # Monday
    groups=None,
    teachers=None,
    classrooms=None,
):
    bells = LessonBells(number=number, start_time=start_time, end_time=end_time)
    return Lesson(
        dates=dates,
        lesson_bells=bells,
        lesson_type=lesson_type,
        subject=subject,
        groups=groups or ["ИКБО-20-23"],
        teachers=teachers or [Teacher(name="Карпов Д.А.")],
        classrooms=classrooms
        or [Classroom(name="А-101", campus=Campus(short_name="В-78"))],
    )


def test_format_outputs_lecture():
    lesson = make_lesson(lesson_type="lecture")
    user_data = {"item": SearchItem(type="teacher", uid=1, name="Карпов Д.А.")}
    blocks = format_outputs([lesson], user_data)
    assert len(blocks) == 1
    block = blocks[0]
    assert "Пара № 1" in block
    assert "09:00 – 10:30" in block
    assert "Математический анализ" in block
    assert "Лекция" in block
    assert "ИКБО-20-23" in block
    assert "Карпов Д.А." in block
    assert "А-101 (В-78)" in block
    assert "Понедельник" in block


def test_format_outputs_all_types():
    type_mappings = {
        "laboratorywork": "Лабораторная",
        "practice": "Практика",
        "individualwork": "Сам. работа",
        "exam": "Экзамен",
        "consultation": "Консультация",
        "coursework": "Курс. раб.",
        "courseproject": "Курс. проект",
        "credit": "Зачет",
        "unknown_type": "Неизвестно",
    }
    user_data = {"item": SearchItem(type="group", uid=10, name="Группа")}
    for api_type, ru_name in type_mappings.items():
        lesson = make_lesson(lesson_type=api_type)
        blocks = format_outputs([lesson], user_data)
        assert len(blocks) == 1
        assert ru_name in blocks[0]


def test_format_outputs_sunday():
    # 2025-09-07 is Sunday (weekday 7)
    lesson = make_lesson(dates=date(2025, 9, 7))
    user_data = {"item": SearchItem(type="teacher", uid=1, name="Test")}
    blocks = format_outputs([lesson], user_data)
    assert len(blocks) == 1
    assert "Воскресенье" in blocks[0]


def test_format_outputs_minimal_fields():
    # Lesson with no groups, no teachers, no classrooms
    lesson = Lesson(
        dates=date(2025, 9, 2),
        lesson_bells=LessonBells(number=2, start_time="10:40", end_time="12:10"),
        subject="Базы данных",
        groups=[],
        teachers=[],
        classrooms=[],
    )
    user_data = {}
    blocks = format_outputs([lesson], user_data)
    assert len(blocks) == 1
    assert "Базы данных" in blocks[0]
    assert "Вторник" in blocks[0]


def test_format_outputs_exception_handling():
    # Provide a malformed lesson object that raises an error
    bad_lesson = MagicMock()
    bad_lesson.dates = "invalid-date"

    user_data = {"item": SearchItem(type="teacher", uid=1, name="Test")}
    blocks = format_outputs([bad_lesson], user_data)
    assert len(blocks) == 1
    assert blocks[0] == "Ошибка при получении расписания"
