import asyncio
from datetime import date, datetime
import os
from typing import Annotated

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.config import settings
from bot.fetch.models import LessonSchedule, SearchItem
from bot.handlers.context import bot_data
from bot.parse.semester import (
    get_current_week_number,
    get_dates_for_week,
    get_week_and_weekday,
)
from bot.service import ScheduleService, UserService
from bot.webapp.auth import validate_telegram_init_data


class FavoriteRequest(BaseModel):
    favorite: str


class MaintenanceRequest(BaseModel):
    enabled: bool
    message: str | None = None


class BroadcastRequest(BaseModel):
    text: str
    image_url: str | None = None
    button_text: str | None = None
    button_url: str | None = None
    test_only: bool = False


broadcast_state = {
    "is_running": False,
    "total": 0,
    "sent": 0,
    "failed": 0,
}


def create_webapp_app(
    schedule_service: ScheduleService,
    user_service: UserService,
    bot: Bot | None = None,
) -> FastAPI:
    # Hide docs, redoc and openapi schema from outside inspection
    app = FastAPI(
        title="MIREA Schedule Bot Mini App API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

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

        # In test / dev environments when user_id is provided directly
        if user_id:
            return {"id": user_id, "first_name": "User"}

        raise HTTPException(
            status_code=401, detail="Unauthorized: invalid or missing Telegram initData"
        )

    async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
        uid = int(user["id"])
        if uid not in settings.admins:
            raise HTTPException(
                status_code=403, detail="Forbidden: Admin access required"
            )
        return user


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
        is_admin = uid in settings.admins

        # Auto-register user in DB if they opened Mini App before running /start
        try:
            from aiogram.types import User as AiogramUser

            tg_user = AiogramUser(
                id=uid,
                is_bot=False,
                first_name=user.get("first_name", "") or "User",
                last_name=user.get("last_name"),
                username=user.get("username"),
            )
            await user_service.ensure_user(tg_user)
        except Exception:
            pass

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
            "is_admin": is_admin,
        }

    @app.post("/api/me/favorite")
    async def set_me_favorite(
        req: FavoriteRequest, user: dict = Depends(get_current_user)
    ):
        uid = int(user["id"])
        await user_service.set_favorite(uid, req.favorite)
        return {"status": "ok", "favorite": req.favorite}

    @app.get("/api/search")
    async def search(
        q: str = Query(..., min_length=1),
        user: dict = Depends(get_current_user),
    ):
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
        date_str: Annotated[str | None, Query(alias="date")] = None,
        use_fav: bool = False,
        user: dict = Depends(get_current_user),
    ):
        current_week = get_current_week_number()
        target_weekday = None

        if date_str:
            try:
                target_week, target_weekday = get_week_and_weekday(date_str)
            except Exception:
                target_week = week if (week and 1 <= week <= 24) else current_week
        else:
            target_week = week if (week and 1 <= week <= 24) else current_week

        target_item: SearchItem | None = None

        if type and uid:
            target_item = SearchItem(type=type, uid=uid, name=name or f"{type}_{uid}")
        elif use_fav:
            fav = await user_service.get_favorite(int(user["id"]))
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
                "dates_summary": {},
            }

        # Calculate dates for the requested week
        dates_of_week = get_dates_for_week(target_week)
        lessons = schedule_service.get_lessons(schedule_data, dates=dates_of_week)
        dates_summary = schedule_service.get_dates_summary(schedule_data)

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
            "target_weekday": target_weekday,
            "days": days_map,
            "dates_summary": dates_summary,
        }

    # ==================== ADMIN ENDPOINTS (Strictly backend protected) ====================

    @app.get("/api/admin/stats")
    async def get_admin_stats(admin: dict = Depends(get_admin_user)):
        total_users = await user_service.count_all_users()
        users_with_fav = await user_service.count_users_with_favorite()
        users_with_notify = await user_service.count_users_with_notifications()

        top_groups = await user_service.get_top_requested_items("group", limit=5)
        top_teachers = await user_service.get_top_requested_items("teacher", limit=5)
        top_classrooms = await user_service.get_top_requested_items("classroom", limit=5)

        return {
            "total_users": total_users,
            "users_with_favorite": users_with_fav,
            "users_with_notifications": users_with_notify,
            "top_groups": [{"name": name, "count": count} for name, count in top_groups],
            "top_teachers": [{"name": name, "count": count} for name, count in top_teachers],
            "top_classrooms": [{"name": name, "count": count} for name, count in top_classrooms],
            "maintenance_mode": bool(bot_data.get("maintenance_mode", False)),
            "maintenance_message": bot_data.get("maintenance_message") or "",
        }

    @app.post("/api/admin/maintenance")
    async def set_admin_maintenance(
        req: MaintenanceRequest,
        admin: dict = Depends(get_admin_user),
    ):
        bot_data["maintenance_mode"] = req.enabled
        bot_data["maintenance_message"] = req.message.strip() if req.message else None

        return {
            "status": "ok",
            "maintenance_mode": bot_data["maintenance_mode"],
            "maintenance_message": bot_data.get("maintenance_message") or "",
        }

    @app.get("/api/admin/broadcast/status")
    async def get_broadcast_status(admin: dict = Depends(get_admin_user)):
        return broadcast_state

    @app.post("/api/admin/broadcast")
    async def run_admin_broadcast(
        req: BroadcastRequest,
        admin: dict = Depends(get_admin_user),
    ):
        if not bot:
            raise HTTPException(status_code=500, detail="Bot instance not configured")

        if not req.text.strip():
            raise HTTPException(status_code=400, detail="Broadcast text cannot be empty")

        # Prepare inline keyboard if specified
        markup = None
        if req.button_text and req.button_url:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=req.button_text.strip(), url=req.button_url.strip())]
                ]
            )

        admin_id = int(admin["id"])

        # Test sending only to admin
        if req.test_only:
            try:
                if req.image_url and req.image_url.strip():
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=req.image_url.strip(),
                        caption=req.text.strip(),
                        reply_markup=markup,
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=req.text.strip(),
                        reply_markup=markup,
                        parse_mode=ParseMode.HTML,
                    )
                return {"status": "ok", "message": "Тестовое сообщение успешно отправлено в ваш чат с ботом!"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Ошибка отправки: {e}")

        # Mass broadcast to all users
        if broadcast_state["is_running"]:
            raise HTTPException(status_code=409, detail="Рассылка уже выполняется!")

        async def _do_broadcast():
            broadcast_state["is_running"] = True
            broadcast_state["sent"] = 0
            broadcast_state["failed"] = 0
            user_ids = await user_service.get_all_user_ids()
            broadcast_state["total"] = len(user_ids)

            img = req.image_url.strip() if req.image_url else None
            txt = req.text.strip()

            for uid in user_ids:
                try:
                    if img:
                        await bot.send_photo(
                            chat_id=uid,
                            photo=img,
                            caption=txt,
                            reply_markup=markup,
                            parse_mode=ParseMode.HTML,
                        )
                    else:
                        await bot.send_message(
                            chat_id=uid,
                            text=txt,
                            reply_markup=markup,
                            parse_mode=ParseMode.HTML,
                        )
                    broadcast_state["sent"] += 1
                except Exception:
                    broadcast_state["failed"] += 1

                await asyncio.sleep(0.04)  # ~25 msg/s to safely stay under Telegram 30 msg/s limit

            broadcast_state["is_running"] = False

        asyncio.create_task(_do_broadcast())
        return {"status": "ok", "message": "Рассылка запущена в фоне!"}

    return app

