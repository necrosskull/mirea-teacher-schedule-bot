import datetime


class Period:
    def __init__(self, year_start, year_end, semester):
        self.year_start = year_start
        self.year_end = year_end
        self.semester = semester


class week:
    week: int


class weekday:
    weekday: int


def get_semester_start_date(year_start, year_end, semester):
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


def get_semester_start_date_from_period():
    current_date = datetime.date.today()
    period = get_period(current_date)
    semester_start_date = get_semester_start_date(
        period.year_start, period.year_end, period.semester
    )
    return semester_start_date


def get_current_week_number() -> int:
    current_date = datetime.date.today()
    semester_start_date = get_semester_start_date_from_period()

    if current_date < semester_start_date:
        semester_start_date = semester_start_date.replace(year=current_date.year - 1)

    week = (current_date - semester_start_date).days // 7 + 1

    return week


def get_week_by_date(date: datetime.date | str) -> int:
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    semester_start_date = get_semester_start_date_from_period()

    if date < semester_start_date:
        semester_start_date = semester_start_date.replace(year=date.year - 1)

    if date < semester_start_date:
        return 1

    week = (date - semester_start_date).days // 7 + 1

    return week


def get_date(week: int, day: int) -> list[datetime.date]:
    semester_start_date = get_semester_start_date_from_period()
    start_weekday = semester_start_date.weekday() + 1
    weekday_diff = day - start_weekday
    days_to_add = (week - 1) * 7
    return [semester_start_date + datetime.timedelta(days=days_to_add + weekday_diff)]


def get_dates_for_week(week_number: int) -> list[datetime.date]:
    semester_start_date = get_semester_start_date_from_period()
    start_weekday = semester_start_date.weekday() + 1
    days_to_add = (week_number - 1) * 7 - start_weekday + 1
    start_date_of_week = semester_start_date + datetime.timedelta(days=days_to_add)
    return [start_date_of_week + datetime.timedelta(days=i) for i in range(7)][:6]


def get_week_and_weekday(date: datetime.date | str) -> tuple[int, int]:
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

    semester_start_date = get_semester_start_date_from_period()

    if date < semester_start_date:
        semester_start_date = semester_start_date.replace(year=date.year - 1)

    if date < semester_start_date:
        return 1, date.weekday() + 1

    week = (date - semester_start_date).days // 7 + 1
    weekday = date.weekday() + 1

    return week, weekday
