from datetime import date, datetime
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.config import settings
from bot.fetch.models import LessonSchedule, SearchItem
from bot.parse.semester import (
    get_current_week_number,
    get_dates_for_week,
    get_week_and_weekday,
)
from bot.service import ScheduleService, UserService
from bot.webapp.auth import validate_telegram_init_data


class FavoriteRequest(BaseModel):
    favorite: str


def create_webapp_app(
    schedule_service: ScheduleService,
    user_service: UserService,
) -> FastAPI:
    app = FastAPI(title="MIREA Schedule Bot Mini App API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    async def get_current_user(
        x_telegram_init_data: Annotated[str | None, Header()] = None,
        init_data: str | None = Query(default=None),
        user_id: int | None = Query(default=None),
    ) -> dict:
        raw_data = x_telegram_init_data or init_data
        if raw_data:
            validated = validate_telegram_init_data(raw_data)
            if validated:
                return validated

        # In dev mode / if token not set or direct user_id provided for testing
        if user_id:
            return {"id": user_id, "first_name": "User"}

        raise HTTPException(
            status_code=401, detail="Unauthorized: invalid or missing Telegram initData"
        )

    @app.get("/")
    @app.get("/app")
    async def serve_webapp():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"status": "ok", "message": "Mini App frontend loaded"}

    @app.get("/api/me")
    async def get_me(user: dict = Depends(get_current_user)):
        uid = int(user["id"])
        fav = await user_service.get_favorite(uid)

        favorite_item = None
        if fav:
            search_items = await schedule_service.search(fav)
            if search_items:
                favorite_item = search_items[0].model_dump()

        return {
            "id": uid,
            "first_name": user.get("first_name", ""),
            "username": user.get("username", ""),
            "favorite": fav,
            "favorite_item": favorite_item,
        }

    @app.post("/api/me/favorite")
    async def set_me_favorite(
        req: FavoriteRequest, user: dict = Depends(get_current_user)
    ):
        uid = int(user["id"])
        await user_service.set_favorite(uid, req.favorite)
        return {"status": "ok", "favorite": req.favorite}

    @app.get("/api/search")
    async def search(q: str = Query(..., min_length=1)):
        items = await schedule_service.search(q)
        if items is None:
            return []
        return [item.model_dump() for item in items]

    @app.get("/api/schedule")
    async def get_schedule(
        type: str | None = None,
        uid: int | None = None,
        name: str | None = None,
        week: int | None = None,
        use_fav: bool = False,
        user: dict | None = None,
        init_data: str | None = Query(default=None),
        x_telegram_init_data: Annotated[str | None, Header()] = None,
    ):
        current_week = get_current_week_number()
        target_week = week if (week and 1 <= week <= 24) else current_week

        target_item: SearchItem | None = None

        if type and uid:
            target_item = SearchItem(type=type, uid=uid, name=name or f"{type}_{uid}")
        elif use_fav:
            # Try to authenticate and fetch user favorite
            raw_data = x_telegram_init_data or init_data
            if raw_data:
                user_info = validate_telegram_init_data(raw_data)
                if user_info and "id" in user_info:
                    fav = await user_service.get_favorite(int(user_info["id"]))
                    if fav:
                        search_res = await schedule_service.search(fav)
                        if search_res:
                            target_item = search_res[0]

        if not target_item:
            raise HTTPException(
                status_code=400,
                detail="Target schedule item not specified and no favorite found",
            )

        schedule_data = await schedule_service.get_schedule(target_item)
        if not schedule_data:
            return {
                "item": target_item.model_dump(),
                "week": target_week,
                "current_week": current_week,
                "days": {},
            }

        # Calculate dates for the requested week
        dates_of_week = get_dates_for_week(target_week)
        lessons = schedule_service.get_lessons(schedule_data, dates=dates_of_week)

        # Group lessons by day (1..6)
        days_map: dict[int, dict] = {}
        for i, dt in enumerate(dates_of_week, 1):
            days_map[i] = {
                "date": dt.isoformat(),
                "weekday": i,
                "lessons": [],
            }

        for l in lessons:
            weekday = l.dates.isoweekday()
            if weekday in days_map:
                days_map[weekday]["lessons"].append(
                    {
                        "number": l.lesson_bells.number,
                        "start_time": l.lesson_bells.start_time,
                        "end_time": l.lesson_bells.end_time,
                        "subject": l.subject,
                        "lesson_type": l.lesson_type,
                        "groups": l.groups,
                        "teachers": [t.name for t in l.teachers],
                        "classrooms": [
                            f"{c.name}" + (f" ({c.campus.short_name})" if c.campus and c.campus.short_name else "")
                            for c in l.classrooms
                        ],
                    }
                )

        return {
            "item": target_item.model_dump(),
            "week": target_week,
            "current_week": current_week,
            "today_date": date.today().isoformat(),
            "today_weekday": date.today().isoweekday(),
            "days": days_map,
        }

    return app
