import enum
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator


class SearchItem(BaseModel):
    type: str
    uid: int
    name: str | None = ""

    @field_validator("type")
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
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = ""
    short_name: str | None = ""

    @field_validator("latitude", "longitude", mode="before")
    def normalize_coords(cls, value):
        if value in ("", None):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class Classroom(BaseModel):
    campus: Campus | None = None
    name: str | None = ""


class Teacher(BaseModel):
    name: str | None = ""


class LessonBells(BaseModel):
    end_time: str | None = ""
    number: int = 0
    start_time: str | None = ""

    @field_validator("number", mode="before")
    def normalize_number(cls, value):
        if value in ("", None):
            return 0

        return value


def validate_dates(value: list[str | date] | None) -> list[date]:
    if not value:
        return []
    result = []
    for item in set(value):
        if isinstance(item, date):
            result.append(item)
        elif isinstance(item, str):
            try:
                result.append(datetime.strptime(item, "%d-%m-%Y").date())
            except ValueError:
                result.append(datetime.strptime(item, "%Y-%m-%d").date())
    return sorted(result)


Dates = Annotated[list[date], BeforeValidator(validate_dates)]


class LessonSchedule(BaseModel):
    classrooms: list[Classroom] = Field(default_factory=list)
    dates: Dates | None = None
    groups: list[str] = Field(default_factory=list)
    lesson_bells: LessonBells
    lesson_type: str | None = ""
    subject: str | None = ""
    teachers: list[Teacher] = Field(default_factory=list)
    type: str | None = ""

    @field_validator("groups", mode="before")
    def normalize_groups(cls, value):
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        return [str(value)]

    @field_validator("classrooms", "teachers", mode="before")
    def normalize_lists(cls, value):
        if value in (None, ""):
            return []
        return value


class Holiday(BaseModel):
    dates: Dates | None = None
    title: str | None = ""
    type: str | None = ""



class Lesson(LessonSchedule):
    dates: date


class ScheduleData(BaseModel):
    data: list[LessonSchedule | Holiday]
