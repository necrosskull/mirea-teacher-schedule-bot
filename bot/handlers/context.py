import asyncio
import datetime
import json
from typing import Any

from bot.fetch.models import SearchItem
from bot.logs.lazy_logger import lazy_logger
from bot.service import StateService

bot_data: dict[str, Any] = {}
_user_data: dict[int, "PersistentUserData"] = {}
_state_service: StateService | None = None

PERSISTED_KEYS = {
    "state",
    "message_id",
    "message_ids",
    "inline_message_id",
    "inline_message_ids",
    "sessions",
    "inline_sessions",
    "awaiting_favorite",
    "week",
    "date",
    "item",
    "available_items",
}


def set_state_service(state_service: StateService):
    global _state_service
    _state_service = state_service


def _encode_value(value: Any):
    if isinstance(value, datetime.date):
        return {"__type": "date", "value": value.isoformat()}

    if isinstance(value, SearchItem):
        return {"__type": "search_item", "value": value.model_dump()}

    if isinstance(value, list):
        return [_encode_value(item) for item in value]

    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}

    return value


def _decode_value(value: Any):
    if isinstance(value, list):
        return [_decode_value(item) for item in value]

    if not isinstance(value, dict):
        return value

    marker = value.get("__type")
    if marker == "date":
        return datetime.date.fromisoformat(value["value"])

    if marker == "search_item":
        return SearchItem(**value["value"])

    return {k: _decode_value(v) for k, v in value.items()}


async def _save_user_data(user_id: int, user_data: dict[str, Any]):
    payload = {}

    for key in PERSISTED_KEYS:
        if key in user_data:
            try:
                payload[key] = _encode_value(user_data[key])
            except Exception:
                continue

    try:
        if _state_service is None:
            return

        await _state_service.save_payload(user_id, json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        lazy_logger.logger.warning(f"_save_user_data failed for user={user_id}: {e}")


async def _load_user_data(user_id: int) -> dict[str, Any]:
    try:
        if _state_service is None:
            return {}

        payload = await _state_service.load_payload(user_id)
        if not payload:
            return {}

        raw_payload = json.loads(payload)
        return {k: _decode_value(v) for k, v in raw_payload.items()}
    except Exception as e:
        lazy_logger.logger.warning(f"_load_user_data failed for user={user_id}: {e}")
        return {}



class PersistentUserData(dict):
    def __init__(self, user_id: int, initial: dict[str, Any]):
        self.user_id = user_id
        super().__init__(initial)

    def _persist(self):
        snapshot = dict(self)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_save_user_data(self.user_id, snapshot))
        except RuntimeError:
            pass

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._persist()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._persist()

    def clear(self):
        super().clear()
        self._persist()

    def pop(self, key, default=None):
        value = super().pop(key, default)
        self._persist()
        return value

    def popitem(self):
        value = super().popitem()
        self._persist()
        return value

    def setdefault(self, key, default=None):
        value = super().setdefault(key, default)
        self._persist()
        return value

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._persist()


async def get_user_data(user_id: int) -> dict[str, Any]:
    if user_id not in _user_data:
        _user_data[user_id] = PersistentUserData(user_id, await _load_user_data(user_id))

    return _user_data[user_id]
