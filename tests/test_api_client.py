import httpx
import pytest
import respx

from bot.api_client import ScheduleApiClient
from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_schedule as fetch_get_schedule
from bot.fetch.search import search_schedule as fetch_search_schedule


@pytest.mark.asyncio
@respx.mock
async def test_schedule_api_client_search_success():
    base_url = "https://api.example.com"
    client = ScheduleApiClient(base_url=base_url)

    # Mock endpoints
    respx.get(f"{base_url}/api/v1/schedule/search/teachers").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"uid": 1, "name": "Карпов Д.А."}]},
        )
    )
    respx.get(f"{base_url}/api/v1/schedule/search/groups").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"uid": 2, "name": "ИКБО-20-23"}]},
        )
    )
    respx.get(f"{base_url}/api/v1/schedule/search/classrooms").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "uid": 3,
                        "name": "А-101",
                        "campus": {"name": "Вернадского 78", "short_name": "В-78"},
                    }
                ]
            },
        )
    )

    results = await client.search("test")
    assert results is not None
    assert len(results) == 3

    # Check classroom campus naming
    classroom_item = next(item for item in results if item.type == "classroom")
    assert classroom_item.name == "А-101 (В-78)"


@pytest.mark.asyncio
@respx.mock
async def test_schedule_api_client_search_empty():
    base_url = "https://api.example.com"
    client = ScheduleApiClient(base_url=base_url)

    respx.get(f"{base_url}/api/v1/schedule/search/teachers").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx.get(f"{base_url}/api/v1/schedule/search/groups").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx.get(f"{base_url}/api/v1/schedule/search/classrooms").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    results = await client.search("nothing")
    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_schedule_api_client_search_http_error():
    base_url = "https://api.example.com"
    client = ScheduleApiClient(base_url=base_url)

    respx.get(f"{base_url}/api/v1/schedule/search/teachers").mock(
        return_value=httpx.Response(500)
    )
    respx.get(f"{base_url}/api/v1/schedule/search/groups").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx.get(f"{base_url}/api/v1/schedule/search/classrooms").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    results = await client.search("test")
    assert results is None


@pytest.mark.asyncio
@respx.mock
async def test_schedule_api_client_get_schedule_success():
    base_url = "https://api.example.com"
    client = ScheduleApiClient(base_url=base_url)

    target = SearchItem(type="teacher", uid=10, name="Иванов")
    mock_data = {
        "data": [
            {
                "subject": "Физика",
                "lesson_bells": {"number": 1, "start_time": "09:00", "end_time": "10:30"},
                "dates": ["01-09-2025"],
                "lesson_type": "lecture",
                "groups": ["ИКБО-01-21"],
                "teachers": [{"name": "Иванов"}],
                "classrooms": [{"name": "А-101"}],
            }
        ]
    }
    respx.get(f"{base_url}/api/v1/schedule/teacher/10").mock(
        return_value=httpx.Response(200, json=mock_data)
    )

    schedule = await client.get_schedule(target)
    assert schedule is not None
    assert len(schedule.data) == 1
    assert schedule.data[0].subject == "Физика"


@pytest.mark.asyncio
@respx.mock
async def test_schedule_api_client_get_schedule_error():
    base_url = "https://api.example.com"
    client = ScheduleApiClient(base_url=base_url)

    target = SearchItem(type="group", uid=999, name="Не найдено")
    respx.get(f"{base_url}/api/v1/schedule/group/999").mock(
        return_value=httpx.Response(404)
    )

    schedule = await client.get_schedule(target)
    assert schedule is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_wrappers(monkeypatch):
    from bot.config import settings
    monkeypatch.setattr(settings, "api_url", "https://api.example.com")

    respx.get("https://api.example.com/api/v1/schedule/search/teachers").mock(
        return_value=httpx.Response(200, json={"results": [{"uid": 1, "name": "Учитель"}]})
    )
    respx.get("https://api.example.com/api/v1/schedule/search/groups").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx.get("https://api.example.com/api/v1/schedule/search/classrooms").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    search_res = await fetch_search_schedule("Учитель")
    assert search_res is not None
    assert len(search_res) == 1

    target = SearchItem(type="teacher", uid=1, name="Учитель")
    respx.get("https://api.example.com/api/v1/schedule/teacher/1").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    sched_res = await fetch_get_schedule(target)
    assert sched_res is not None
    assert sched_res.data == []
