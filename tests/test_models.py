from datetime import date

import pytest
from pydantic import ValidationError

from bot.fetch.models import (
    Campus,
    Classroom,
    Holiday,
    Lesson,
    LessonBells,
    LessonSchedule,
    ScheduleData,
    ScheduleEndpoints,
    SearchItem,
    SearchResults,
    Teacher,
    validate_dates,
)


def test_search_item_singularize_type():
    item1 = SearchItem(type="teachers", uid=1, name="Иванов И.И.")
    assert item1.type == "teacher"

    item2 = SearchItem(type="groups", uid=2, name="ИКБО-01-21")
    assert item2.type == "group"

    item3 = SearchItem(type="classrooms", uid=3, name="А-101")
    assert item3.type == "classroom"

    item4 = SearchItem(type="teacher", uid=4, name="Петров П.П.")
    assert item4.type == "teacher"


def test_schedule_endpoints():
    assert ScheduleEndpoints.teachers.value == "teachers"
    assert ScheduleEndpoints.groups.value == "groups"
    assert ScheduleEndpoints.classrooms.value == "classrooms"


def test_campus_model():
    c1 = Campus()
    assert c1.latitude is None
    assert c1.longitude is None
    assert c1.name == ""

    c2 = Campus(latitude=55.75, longitude="37.61", name="Main", short_name="M")
    assert c2.latitude == 55.75
    assert c2.longitude == 37.61

    c3 = Campus(latitude="", longitude="invalid")
    assert c3.latitude is None
    assert c3.longitude is None


def test_lesson_bells_normalize_number():
    b1 = LessonBells(number=1, start_time="09:00", end_time="10:30")
    assert b1.number == 1

    b2 = LessonBells(number="", start_time="10:40", end_time="12:10")
    assert b2.number == 0

    b3 = LessonBells(number=None)
    assert b3.number == 0


def test_validate_dates():
    assert validate_dates(None) == []
    assert validate_dates([]) == []

    dates = validate_dates(["01-09-2025", "02-09-2025", "01-09-2025"])
    assert len(dates) == 2
    assert date(2025, 9, 1) in dates
    assert date(2025, 9, 2) in dates

    iso_dates = validate_dates(["2025-09-10", date(2025, 9, 11)])
    assert date(2025, 9, 10) in iso_dates
    assert date(2025, 9, 11) in iso_dates


def test_lesson_schedule_model():
    bells = LessonBells(number=1, start_time="09:00", end_time="10:30")
    ls = LessonSchedule(
        classrooms=[Classroom(name="А-101", campus=Campus(name="Вернадка", short_name="В-78"))],
        dates=["01-09-2025"],
        groups="ИКБО-01-21",  # string should be normalized to list
        lesson_bells=bells,
        lesson_type="lecture",
        subject="Физика",
        teachers=[Teacher(name="Сидоров С.С.")],
        type="lesson",
    )
    assert ls.groups == ["ИКБО-01-21"]
    assert len(ls.classrooms) == 1
    assert ls.classrooms[0].name == "А-101"
    assert ls.classrooms[0].campus.short_name == "В-78"
    assert len(ls.teachers) == 1
    assert ls.teachers[0].name == "Сидоров С.С."


def test_lesson_schedule_empty_lists():
    bells = LessonBells(number=1)
    ls = LessonSchedule(
        classrooms=None,
        dates=None,
        groups=None,
        lesson_bells=bells,
        teachers=None,
    )
    assert ls.classrooms == []
    assert ls.groups == []
    assert ls.teachers == []


def test_lesson_model():
    bells = LessonBells(number=2)
    l = Lesson(
        dates=date(2025, 9, 1),
        lesson_bells=bells,
        subject="Матлогика",
    )
    assert l.dates == date(2025, 9, 1)
    assert l.subject == "Матлогика"


def test_holiday_model():
    h = Holiday(
        dates=["01-01-2026"],
        title="Новый год",
        type="holiday",
    )
    assert h.title == "Новый год"
    assert h.dates == [date(2026, 1, 1)]


def test_schedule_data():
    bells = LessonBells(number=1)
    ls = LessonSchedule(lesson_bells=bells, subject="Информатика")
    h = Holiday(title="Выходной")
    sd = ScheduleData(data=[ls, h])
    assert len(sd.data) == 2


def test_search_results_iteration():
    sr = SearchResults(
        teachers=[SearchItem(type="teacher", uid=1, name="T1")],
        groups=[SearchItem(type="group", uid=2, name="G1")],
        classrooms=None,
    )
    items = [item for _, val in sr if val for item in val]
    assert len(items) == 2
    assert items[0].name == "T1"
    assert items[1].name == "G1"
