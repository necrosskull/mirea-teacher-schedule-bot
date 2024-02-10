import enum
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, validator


class SearchItem(BaseModel):
    type: str
    uid: int
    name: str | None = ""

    @validator("type", pre=True, always=True)
    def singularize_type(cls, value):
        return value[:-1] if value.endswith("s") else value


class ScheduleEndpoints(enum.Enum):
    teachers = "teachers"
    groups = "groups"
    classrooms = "classrooms"


class SearchResults(BaseModel):
    teachers: list[SearchItem] | None = None
    groups: list[SearchItem] | None = None
    classrooms: list[SearchItem] | None = None


class Campus(BaseModel):
    latitude: float | None = ""
    longitude: float | None = ""
    name: str | None = ""
    short_name: str | None = ""


class Classroom(BaseModel):
    campus: Campus | None = None
    name: str | None = ""


class Teacher(BaseModel):
    name: str | None = ""


class LessonBells(BaseModel):
    end_time: str | None = ""
    number: int | None = ""
    start_time: str | None = ""


def validate_dates(value: list[str]) -> list[date]:
    return [datetime.strptime(date, "%d-%m-%Y").date() for date in set(value)]


Dates = Annotated[list[date], BeforeValidator(validate_dates)]


class LessonSchedule(BaseModel):
    classrooms: list[Classroom] | None = None
    dates: Dates | None = None
    groups: list[str] | None = ""
    lesson_bells: LessonBells
    lesson_type: str | None = ""
    subject: str | None = ""
    teachers: list[Teacher] | None = None
    type: str | None = ""


class Holiday(BaseModel):
    dates: Dates | None = None
    title: str | None = ""
    type: str | None = ""


class Lesson(LessonSchedule):
    dates: date


class ScheduleData(BaseModel):
    data: list[LessonSchedule | Holiday]
