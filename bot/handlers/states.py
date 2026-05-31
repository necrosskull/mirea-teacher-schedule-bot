from aiogram.fsm.state import State, StatesGroup

ITEM_CLARIFY, GETWEEK, GETDAY = map(chr, range(3))


class DialogStates(StatesGroup):
    item_clarify = State()
    get_week = State()
    get_day = State()


class FavoriteStates(StatesGroup):
    awaiting_favorite = State()


class InlineDialogStates(StatesGroup):
    ask_week = State()
    ask_day = State()


class NotificationStates(StatesGroup):
    awaiting_query = State()
    awaiting_item = State()
    awaiting_time = State()


TARGET_TO_STATE = {
    ITEM_CLARIFY: DialogStates.item_clarify,
    GETWEEK: DialogStates.get_week,
    GETDAY: DialogStates.get_day,
}
