from datetime import date

from bot.parse.semester import (
    Period,
    get_current_week_number,
    get_date,
    get_dates_for_week,
    get_period,
    get_semester_start_date,
    get_semester_start_date_from_period,
    get_week_and_weekday,
    get_week_by_date,
)


def test_period_class():
    p = Period(2025, 2026, 1)
    assert p.year_start == 2025
    assert p.year_end == 2026
    assert p.semester == 1


def test_get_semester_start_date_semester_1():
    # 2024-09-01 was a Sunday (weekday() == 6), so should shift to 2024-09-02
    start_2024 = get_semester_start_date(2024, 2025, 1)
    assert start_2024 == date(2024, 9, 2)

    # 2025-09-01 is a Monday
    start_2025 = get_semester_start_date(2025, 2026, 1)
    assert start_2025 == date(2025, 9, 1)


def test_get_semester_start_date_semester_2():
    # 2025-02-01 + 8 days = 2025-02-09 (Sunday, weekday() == 6), shifted to Feb 10
    start_2025 = get_semester_start_date(2024, 2025, 2)
    assert start_2025 == date(2025, 2, 10)

    # 2026-02-01 + 8 days = 2026-02-09 (Monday, weekday() == 0)
    start_2026 = get_semester_start_date(2025, 2026, 2)
    assert start_2026 == date(2026, 2, 9)


def test_get_period():
    p_autumn = get_period(date(2025, 9, 15))
    assert p_autumn.year_start == 2025
    assert p_autumn.year_end == 2026
    assert p_autumn.semester == 1

    p_jan = get_period(date(2026, 1, 10))
    assert p_jan.year_start == 2025
    assert p_jan.year_end == 2026
    assert p_jan.semester == 1

    p_spring = get_period(date(2026, 3, 1))
    assert p_spring.year_start == 2025
    assert p_spring.year_end == 2026
    assert p_spring.semester == 2


def test_get_semester_start_date_from_period():
    dt = date(2025, 10, 1)
    start_date = get_semester_start_date_from_period(dt)
    assert start_date == date(2025, 9, 1)


def test_get_week_by_date():
    # Semester 1 starts 2025-09-01
    assert get_week_by_date(date(2025, 9, 1)) == 1
    assert get_week_by_date(date(2025, 9, 7)) == 1
    assert get_week_by_date(date(2025, 9, 8)) == 2
    assert get_week_by_date("2025-09-15") == 3

    # Date before semester start returns 1
    assert get_week_by_date(date(2025, 8, 25)) == 1


def test_get_week_and_weekday():
    # 2025-09-01 is Monday (weekday 1)
    week, weekday = get_week_and_weekday(date(2025, 9, 1))
    assert week == 1
    assert weekday == 1

    # 2025-09-07 is Sunday (weekday 7)
    week, weekday = get_week_and_weekday("2025-09-07")
    assert week == 1
    assert weekday == 7

    # Before semester start
    w_early, d_early = get_week_and_weekday("2025-08-30")
    assert w_early == 1
    assert d_early == 6  # Saturday


def test_get_dates_for_week():
    ref_date = date(2025, 9, 1)  # Monday, semester start
    dates_w1 = get_dates_for_week(1, reference_date=ref_date)
    assert len(dates_w1) == 6
    assert dates_w1[0] == date(2025, 9, 1)
    assert dates_w1[5] == date(2025, 9, 6)

    dates_w2 = get_dates_for_week(2, reference_date=ref_date)
    assert dates_w2[0] == date(2025, 9, 8)
    assert dates_w2[5] == date(2025, 9, 13)


def test_get_date():
    ref_date = date(2025, 9, 1)
    d = get_date(1, 1, reference_date=ref_date)
    assert d == [date(2025, 9, 1)]

    d_wed = get_date(1, 3, reference_date=ref_date)
    assert d_wed == [date(2025, 9, 3)]


def test_get_current_week_number():
    curr_week = get_current_week_number()
    assert isinstance(curr_week, int)
    assert curr_week >= 1
