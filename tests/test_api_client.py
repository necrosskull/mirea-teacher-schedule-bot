import json
from datetime import date

import httpx
import pytest
import respx

from bot.api_client import ScheduleApiClient
from bot.config import settings
from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_schedule as fetch_get_schedule
from bot.fetch.search import search_schedule as fetch_search_schedule

BASE_URL = "https://supabase.example.com"
SEARCH_URL = f"{BASE_URL}/rest/v1/rpc/search_schedule_targets"
SCHEDULE_URL = f"{BASE_URL}/rest/v1/rpc/get_schedule_for_entity"
API_KEY = "sb_publishable_test_key"


def make_client(**kwargs) -> ScheduleApiClient:
    return ScheduleApiClient(base_url=BASE_URL, api_key=API_KEY, **kwargs)


def search_response(target_type: str) -> list[dict]:
    payloads = {
        "group": [
            {
                "target_type": "group",
                "external_id": "729",
                "target_title": "ИКБО-10-23",
                "full_title": "ИКБО-10-23",
            }
        ],
        "teacher": [
            {
                "target_type": "teacher",
                "external_id": "539",
                "target_title": "Иванов А. Д.",
                "full_title": "Иванов Артем Дмитриевич",
            }
        ],
        "classroom": [
            {
                "target_type": "classroom",
                "external_id": "66",
                "target_title": "А-1 (В-78)",
                "full_title": "А-1 (В-78)",
            }
        ],
    }
    return payloads[target_type]


@pytest.mark.asyncio
@respx.mock
async def test_search_maps_supabase_targets():
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(200, json=search_response(payload["p_target_type"]))

    respx.post(SEARCH_URL).mock(side_effect=handler)

    results = await make_client().search("ИКБО")

    assert results is not None
    assert {(item.type, item.uid) for item in results} == {
        ("group", 729),
        ("teacher", 539),
        ("classroom", 66),
    }
    group_item = next(item for item in results if item.type == "group")
    assert group_item.name == "ИКБО-10-23"
    # Classroom campus is already baked into target_title by the backend.
    classroom_item = next(item for item in results if item.type == "classroom")
    assert classroom_item.name == "А-1 (В-78)"

    # Every target type is queried in a single round trip and authenticated
    # with the publishable key.
    assert {json.loads(r.content)["p_target_type"] for r in seen_requests} == {
        "group",
        "teacher",
        "classroom",
    }
    for request in seen_requests:
        assert request.headers["apikey"] == API_KEY
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert json.loads(request.content)["p_organization_id"] == settings.organization_id
        assert json.loads(request.content)["p_limit"] == settings.schedule_search_limit


@pytest.mark.asyncio
@respx.mock
async def test_search_empty_result():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    results = await make_client().search("nothing")
    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_search_all_targets_fail_returns_none():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(500))

    results = await make_client().search("test")
    assert results is None


@pytest.mark.asyncio
@respx.mock
async def test_search_partial_failure_returns_available_targets():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["p_target_type"] == "teacher":
            return httpx.Response(500)
        return httpx.Response(200, json=search_response(payload["p_target_type"]))

    respx.post(SEARCH_URL).mock(side_effect=handler)

    results = await make_client().search("test")
    assert results is not None
    assert {item.type for item in results} == {"group", "classroom"}


@pytest.mark.asyncio
@respx.mock
async def test_search_skips_non_numeric_external_id():
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["p_target_type"] != "group":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {"target_type": "group", "external_id": "abc", "target_title": "Nope"},
                {"target_type": "group", "external_id": "12", "target_title": "Group"},
            ],
        )

    respx.post(SEARCH_URL).mock(side_effect=handler)

    results = await make_client().search("x")
    assert results is not None
    assert [(item.type, item.uid) for item in results] == [("group", 12)]


@pytest.mark.asyncio
@respx.mock
async def test_search_deduplicates_results():
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["p_target_type"] != "group":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {"target_type": "group", "external_id": "12", "target_title": "Group"},
                {"target_type": "group", "external_id": "12", "target_title": "Group"},
            ],
        )

    respx.post(SEARCH_URL).mock(side_effect=handler)

    results = await make_client().search("x")
    assert results is not None
    assert len(results) == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_schedule_parses_wire_payload():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=[
                {
                    "type": "__lesson_schedule__",
                    "uid": "9b94fbac-a628-5228-aa9a-21ca6550c102",
                    "subject": "Физика",
                    "lesson_bells": {
                        "number": 1,
                        "start_time": "09:00",
                        "end_time": "10:30",
                    },
                    "dates": ["01-09-2026"],
                    "lesson_type": "lecture",
                    "groups": ["ИКБО-10-23"],
                    "group_entities": [{"uid": "729", "name": "ИКБО-10-23"}],
                    "teachers": [{"uid": "539", "name": "Иванов Артем Дмитриевич"}],
                    "classrooms": [
                        {
                            "uid": "147",
                            "name": "И-212-г",
                            "campus": {"name": "Вернадского 78", "short_name": "В-78"},
                        }
                    ],
                },
                {
                    "type": "__holiday__",
                    "title": "День знаний",
                    "dates": ["01-09-2026"],
                },
                {
                    "type": "__calendar_event__",
                    "kind": "event",
                    "title": "Конференция",
                    "dates": ["02-09-2026"],
                },
            ],
        )

    respx.post(SCHEDULE_URL).mock(side_effect=handler)

    target = SearchItem(type="teacher", uid=10, name="Иванов")
    schedule = await make_client().get_schedule(
        target, date_from=date(2026, 9, 1), date_to=date(2027, 1, 31)
    )

    assert schedule is not None
    assert len(schedule.data) == 3
    lesson = schedule.data[0]
    assert lesson.subject == "Физика"
    assert lesson.dates == [date(2026, 9, 1)]
    assert lesson.teachers[0].name == "Иванов Артем Дмитриевич"
    assert lesson.classrooms[0].campus.short_name == "В-78"

    assert captured["p_entity_type"] == "teacher"
    assert captured["p_entity"] == "10"
    assert captured["p_organization_id"] == settings.organization_id
    assert captured["p_date_from"] == "2026-09-01"
    assert captured["p_date_to"] == "2027-01-31"


@pytest.mark.asyncio
@respx.mock
async def test_get_schedule_http_error_returns_none():
    respx.post(SCHEDULE_URL).mock(return_value=httpx.Response(404))

    schedule = await make_client().get_schedule(
        SearchItem(type="group", uid=999, name="Не найдено")
    )
    assert schedule is None


@pytest.mark.asyncio
@respx.mock
async def test_get_schedule_unexpected_payload_returns_none():
    respx.post(SCHEDULE_URL).mock(
        return_value=httpx.Response(200, json={"detail": "not an array"})
    )

    schedule = await make_client().get_schedule(
        SearchItem(type="group", uid=999, name="Группа")
    )
    assert schedule is None


@pytest.mark.asyncio
async def test_client_without_credentials_returns_none():
    client = ScheduleApiClient(base_url="", api_key="")

    assert client.configured is False
    assert await client.search("ИКБО") is None
    assert (
        await client.get_schedule(SearchItem(type="group", uid=729, name="ИКБО-10-23"))
        is None
    )


@pytest.mark.asyncio
@respx.mock
async def test_fetch_wrappers(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", BASE_URL)
    monkeypatch.setattr(settings, "supabase_key", API_KEY)

    respx.post(SEARCH_URL).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=[
                {
                    "target_type": "teacher",
                    "external_id": "1",
                    "target_title": "Учитель",
                }
            ]
            if json.loads(request.content)["p_target_type"] == "teacher"
            else [],
        )
    )

    search_res = await fetch_search_schedule("Учитель")
    assert search_res is not None
    assert len(search_res) == 1

    target = SearchItem(type="teacher", uid=1, name="Учитель")
    respx.post(SCHEDULE_URL).mock(return_value=httpx.Response(200, json=[]))
    sched_res = await fetch_get_schedule(target)
    assert sched_res is not None
    assert sched_res.data == []
