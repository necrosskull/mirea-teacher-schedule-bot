import enum


class EInlineStep(enum.Enum):
    ask_teacher = 0
    ask_day = 1
    ask_week = 2
    completed = 3
    unk_error = -1
