import enum
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from bot.logs.lazy_logger import lazy_logger


class SearchItem(BaseModel):
    type: str
    uid: int
    name: str | None = ""

    @field_validator("type")
    def singularize_type(cls, value):
        value = value.strip().lower()
        return value[:-1] if value.endswith("s") else value


class ScheduleTargetType(str, enum.Enum):
    """Entity kinds accepted by the schedule RPCs (singular, as in the wire API)."""

    GROUP = "group"
    TEACHER = "teacher"
    CLASSROOM = "classroom"


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


class CalendarEvent(BaseModel):
    """Non-lesson calendar item emitted by the Supabase schedule API.

    The bot does not render these, but they must not break schedule parsing.
    """

    dates: Dates | None = None
    title: str | None = ""
    type: str | None = ""
    kind: str | None = ""
    description: str | None = ""
    location: str | None = ""
    is_all_day: bool | None = None
    uid: str | None = ""
    starts_at: str | None = ""
    ends_at: str | None = ""


class Lesson(LessonSchedule):
    dates: date


class ScheduleData(BaseModel):
    data: list[LessonSchedule | Holiday | CalendarEvent] = Field(default_factory=list)

    @classmethod
    def from_wire(cls, payload: list[dict] | None) -> "ScheduleData":
        """Build schedule data from the Supabase ``get_schedule_for_entity`` array.

        The RPC returns a mixed array of ``__lesson_schedule__``, ``__holiday__``
        and ``__calendar_event__`` items; each kind is parsed explicitly so an
        unexpected item cannot be silently mistaken for a lesson.
        """
        items: list[LessonSchedule | Holiday | CalendarEvent] = []
        for raw in payload or []:
            item_type = raw.get("type")
            try:
                if item_type == "__holiday__":
                    items.append(Holiday(**raw))
                elif item_type == "__calendar_event__":
                    items.append(CalendarEvent(**raw))
                elif item_type == "__lesson_schedule__" or "lesson_bells" in raw:
                    items.append(LessonSchedule(**raw))
                # else: unknown future item kinds are ignored instead of
                # failing the whole schedule.
            except Exception as error:  # noqa: BLE001 - one bad item must not break the schedule
                lazy_logger.logger.warning(
                    f"ScheduleData.from_wire skipped malformed {item_type!r} item: {error}"
                )
                continue
        return cls(data=items)
