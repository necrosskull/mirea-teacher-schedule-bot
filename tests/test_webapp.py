import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.fetch.models import LessonBells, LessonSchedule, ScheduleData, SearchItem
from bot.service import ScheduleService, UserService
from bot.webapp.auth import validate_telegram_init_data
from bot.webapp.server import create_webapp_app


def create_valid_init_data(token: str, user_dict: dict, auth_date: int | None = None) -> str:
    if auth_date is None:
        auth_date = int(time.time())

    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user_dict, separators=(",", ":")),
    }

    data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    params["hash"] = calc_hash
    return "&".join(f"{k}={params[k]}" for k in params)


def test_auth_validation():
    token = "123456:TEST_TOKEN_SECRET"
    user_info = {"id": 12345, "first_name": "Тест", "username": "testuser"}

    # 1. Valid initData
    valid_data = create_valid_init_data(token, user_info)
    res = validate_telegram_init_data(valid_data, bot_token=token)
    assert res is not None
    assert res["id"] == 12345
    assert res["first_name"] == "Тест"

    # 2. Tampered hash
    tampered = valid_data.replace("hash=", "hash=wrong")
    assert validate_telegram_init_data(tampered, bot_token=token) is None

    # 3. Expired auth_date (older than 24h)
    expired_data = create_valid_init_data(token, user_info, auth_date=int(time.time()) - 90000)
    assert validate_telegram_init_data(expired_data, bot_token=token) is None

    # 4. Empty / malformed
    assert validate_telegram_init_data("", bot_token=token) is None
    assert validate_telegram_init_data("foo=bar", bot_token=token) is None


@pytest.mark.asyncio
async def test_webapp_api_endpoints():
    token = "123456:SECRET_BOT_TOKEN"
    user_info = {"id": 777, "first_name": "Иван"}
    valid_init_data = create_valid_init_data(token, user_info)

    # Mock ScheduleService
    mock_sched_service = MagicMock(spec=ScheduleService)
    mock_sched_service.search = AsyncMock()
    mock_sched_service.get_schedule = AsyncMock()
    mock_sched_service.get_lessons = MagicMock()

    # Mock UserService
    mock_user_service = MagicMock(spec=UserService)
    mock_user_service.get_favorite = AsyncMock(return_value="КТСО-01-22")
    mock_user_service.set_favorite = AsyncMock()

    app = create_webapp_app(mock_sched_service, mock_user_service)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Root & App routes
        r1 = await client.get("/")
        assert r1.status_code == 200
        r2 = await client.get("/app")
        assert r2.status_code == 200

        # Hidden documentation checks (must be 404)
        r_docs = await client.get("/docs")
        assert r_docs.status_code == 404
        r_redoc = await client.get("/redoc")
        assert r_redoc.status_code == 404
        r_openapi = await client.get("/openapi.json")
        assert r_openapi.status_code == 404

        # 2. /api/me without auth -> 401
        r_unauth = await client.get("/api/me")
        assert r_unauth.status_code == 401

        # 3. /api/me with user_id query (test fallback)
        r_me_test = await client.get("/api/me?user_id=777")
        assert r_me_test.status_code == 200
        data_me = r_me_test.json()
        assert data_me["id"] == 777
        assert data_me["favorite"] == "КТСО-01-22"
        assert "is_admin" in data_me

        # 4. /api/me/favorite
        r_fav = await client.post(
            "/api/me/favorite?user_id=777",
            json={"favorite": "ИКБО-20-23"},
        )
        assert r_fav.status_code == 200
        mock_user_service.set_favorite.assert_called_once_with(777, "ИКБО-20-23")

        # 5. /api/search without auth -> 401
        r_search_unauth = await client.get("/api/search?q=Афан")
        assert r_search_unauth.status_code == 401

        # /api/search with auth -> 200
        mock_sched_service.search.return_value = [
            SearchItem(type="teacher", uid=1, name="Афанасьев М.С.")
        ]
        r_search = await client.get("/api/search?q=Афан&user_id=777")
        assert r_search.status_code == 200
        items = r_search.json()
        assert len(items) == 1
        assert items[0]["name"] == "Афанасьев М.С."

        # 6. /api/schedule without auth -> 401
        r_sched_unauth = await client.get("/api/schedule?type=group&uid=10&name=КТСО-01-22&week=1")
        assert r_sched_unauth.status_code == 401

        # /api/schedule with auth and explicit type/uid
        item = SearchItem(type="group", uid=10, name="КТСО-01-22")
        lesson = LessonSchedule(
            dates=["01-09-2025"],
            lesson_bells=LessonBells(number=1, start_time="09:00", end_time="10:30"),
            subject="Физика",
        )
        mock_sched_service.get_schedule.return_value = ScheduleData(data=[lesson])
        mock_sched_service.get_lessons.return_value = []
        mock_sched_service.get_dates_summary.return_value = {"2025-09-01": ["lecture"]}

        r_sched = await client.get("/api/schedule?type=group&uid=10&name=КТСО-01-22&week=1&user_id=777")
        assert r_sched.status_code == 200
        sched_json = r_sched.json()
        assert sched_json["item"]["name"] == "КТСО-01-22"
        assert "days" in sched_json
        assert "dates_summary" in sched_json

        # Test date parameter
        r_date = await client.get("/api/schedule?type=group&uid=10&name=КТСО-01-22&date=2025-09-01&user_id=777")
        assert r_date.status_code == 200

        # 7. /api/schedule with missing params -> 400
        r_bad = await client.get("/api/schedule?user_id=777")
        assert r_bad.status_code == 400

        # 8. Admin endpoints authorization
        # Non-admin user (777 is not in admins by default)
        from bot.config import settings
        settings.admins = [999]

        r_admin_stats_fail = await client.get("/api/admin/stats?user_id=777")
        assert r_admin_stats_fail.status_code == 403

        r_admin_maint_fail = await client.post(
            "/api/admin/maintenance?user_id=777",
            json={"enabled": True, "message": "Test"},
        )
        assert r_admin_maint_fail.status_code == 403

        # Admin user (999 is in admins)
        mock_user_service.count_all_users.return_value = 150
        mock_user_service.count_users_with_favorite.return_value = 80
        mock_user_service.count_users_with_notifications.return_value = 45
        mock_user_service.get_top_requested_items.return_value = [("ИКБО-10-23", 42)]

        r_admin_stats_ok = await client.get("/api/admin/stats?user_id=999")
        assert r_admin_stats_ok.status_code == 200
        stats_data = r_admin_stats_ok.json()
        assert stats_data["total_users"] == 150
        assert stats_data["users_with_favorite"] == 80
        assert stats_data["users_with_notifications"] == 45

        r_admin_maint_ok = await client.post(
            "/api/admin/maintenance?user_id=999",
            json={"enabled": True, "message": "Технические работы"},
        )
        assert r_admin_maint_ok.status_code == 200
        maint_data = r_admin_maint_ok.json()
        assert maint_data["maintenance_mode"] is True
        assert maint_data["maintenance_message"] == "Технические работы"

