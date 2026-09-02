import asyncio
import datetime
from unittest.mock import AsyncMock

import pytest

from bot.fetch.models import SearchItem
from bot.handlers.context import (
    PersistentUserData,
    _decode_value,
    _encode_value,
    _load_user_data,
    _save_user_data,
    get_user_data,
    set_state_service,
)
from bot.service import StateService


def test_encode_decode_value():
    d = datetime.date(2025, 9, 1)
    encoded_date = _encode_value(d)
    assert encoded_date == {"__type": "date", "value": "2025-09-01"}
    assert _decode_value(encoded_date) == d

    item = SearchItem(type="teacher", uid=10, name="Карпов")
    encoded_item = _encode_value(item)
    assert encoded_item["__type"] == "search_item"
    assert encoded_item["value"]["uid"] == 10
    decoded_item = _decode_value(encoded_item)
    assert isinstance(decoded_item, SearchItem)
    assert decoded_item.uid == 10
    assert decoded_item.name == "Карпов"

    # Nested structures
    complex_val = {
        "date": d,
        "items": [item],
        "simple": 123,
    }
    encoded_complex = _encode_value(complex_val)
    decoded_complex = _decode_value(encoded_complex)
    assert decoded_complex["date"] == d
    assert decoded_complex["items"][0].uid == 10
    assert decoded_complex["simple"] == 123


@pytest.mark.asyncio
async def test_save_and_load_user_data(state_service: StateService):
    set_state_service(state_service)

    user_id = 7777
    user_data = {
        "week": 5,
        "item": SearchItem(type="group", uid=1, name="ИКБО-20-23"),
        "non_persisted_key": "ignore_me",
    }

    await _save_user_data(user_id, user_data)
    loaded = await _load_user_data(user_id)

    assert loaded["week"] == 5
    assert isinstance(loaded["item"], SearchItem)
    assert loaded["item"].name == "ИКБО-20-23"
    assert "non_persisted_key" not in loaded


@pytest.mark.asyncio
async def test_persistent_user_data_mutations(state_service: StateService):
    set_state_service(state_service)

    user_id = 8888
    pdata = PersistentUserData(user_id, {})

    pdata["week"] = 3
    pdata.update({"message_id": 123})
    pdata.setdefault("awaiting_favorite", False)
    assert pdata.pop("message_id") == 123
    pdata["message_id"] = 456
    pdata.popitem()

    del pdata["week"]
    pdata["week"] = 10
    pdata.clear()
    assert len(pdata) == 0


@pytest.mark.asyncio
async def test_get_user_data_singleton(state_service: StateService):
    set_state_service(state_service)

    user_id = 9999
    data1 = await get_user_data(user_id)
    data1["week"] = 4

    data2 = await get_user_data(user_id)
    assert data2["week"] == 4
    assert data1 is data2
