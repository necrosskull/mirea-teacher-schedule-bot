import enum


class EInlineStep(enum.Enum):
    ask_teacher = 0
    ask_week = 1
    ask_day = 2
    completed = 3
    unk_error = -1
