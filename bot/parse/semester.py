import datetime


class Period:
    def __init__(self, year_start: int, year_end: int, semester: int):
        self.year_start = year_start
        self.year_end = year_end
        self.semester = semester


def get_semester_start_date(year_start: int, year_end: int, semester: int) -> datetime.date:
    if semester == 1:
        start_date = datetime.date(year_start, 9, 1)
        if start_date.weekday() == 6:
            start_date += datetime.timedelta(days=1)
        return start_date

    start_date = datetime.date(year_end, 2, 1)
    start_date += datetime.timedelta(days=8)

    if start_date.weekday() == 6:
        start_date += datetime.timedelta(days=1)

    return start_date


def get_period(date: datetime.date) -> Period:
    if date.month >= 8:
        return Period(date.year, date.year + 1, 1)
    elif date.month < 2:  # Если ещё январь, то это первый семестр
        return Period(date.year - 1, date.year, 1)
    else:
        return Period(date.year - 1, date.year, 2)


def get_semester_start_date_from_period(target_date: datetime.date | None = None) -> datetime.date:
    current_date = target_date if target_date is not None else datetime.date.today()
    period = get_period(current_date)
    return get_semester_start_date(
        period.year_start, period.year_end, period.semester
    )


def get_current_week_number() -> int:
    return get_week_by_date(datetime.date.today())


def get_week_by_date(date: datetime.date | str) -> int:
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    semester_start_date = get_semester_start_date_from_period(date)

    if date < semester_start_date:
        return 1

    week = (date - semester_start_date).days // 7 + 1
    return max(1, week)


def get_date(week: int, day: int, reference_date: datetime.date | None = None) -> list[datetime.date]:
    semester_start_date = get_semester_start_date_from_period(reference_date)
    start_weekday = semester_start_date.weekday() + 1
    weekday_diff = day - start_weekday
    days_to_add = (week - 1) * 7
    return [semester_start_date + datetime.timedelta(days=days_to_add + weekday_diff)]


def get_dates_for_week(
    week_number: int, reference_date: datetime.date | None = None
) -> list[datetime.date]:
    semester_start_date = get_semester_start_date_from_period(reference_date)
    start_weekday = semester_start_date.weekday() + 1
    days_to_add = (week_number - 1) * 7 - start_weekday + 1
    start_date_of_week = semester_start_date + datetime.timedelta(days=days_to_add)
    return [start_date_of_week + datetime.timedelta(days=i) for i in range(7)][:6]


def get_week_and_weekday(date: datetime.date | str) -> tuple[int, int]:
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    weekday = date.weekday() + 1
    semester_start_date = get_semester_start_date_from_period(date)

    if date < semester_start_date:
        return 1, weekday

    week = (date - semester_start_date).days // 7 + 1
    return max(1, week), weekday

