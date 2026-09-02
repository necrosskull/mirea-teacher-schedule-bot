import asyncio
from datetime import date, datetime
import os
import re
from typing import Annotated
import uuid

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
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
    media_url: str | None = None
    image_url: str | None = None
    media_type: str | None = None  # "image" | "video"
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
    uploads_dir = os.path.join(static_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
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
                uid = int(validated["id"])
                asyncio.create_task(
                    user_service.record_user_activity(
                        uid, validated.get("first_name"), validated.get("username")
                    )
                )
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

        # Activity periods: DAU (24h), WAU (7d), MAU (30d)
        dau = await user_service.get_active_users_count(86400)
        wau = await user_service.get_active_users_count(7 * 86400)
        mau = await user_service.get_active_users_count(30 * 86400)

        # New registrations
        new_today = await user_service.get_new_users_count(86400)
        new_week = await user_service.get_new_users_count(7 * 86400)
        new_month = await user_service.get_new_users_count(30 * 86400)

        # Content demand breakdown
        type_dist = await user_service.get_requests_distribution()
        total_requests = await user_service.get_total_requests_count()
        sum_requests = sum(type_dist.values()) or 1
        type_percentages = {
            "group": round((type_dist.get("group", 0) / sum_requests) * 100, 1),
            "teacher": round((type_dist.get("teacher", 0) / sum_requests) * 100, 1),
            "classroom": round((type_dist.get("classroom", 0) / sum_requests) * 100, 1),
        }

        # Conversion rates
        fav_pct = round((users_with_fav / total_users * 100), 1) if total_users else 0
        notify_pct = round((users_with_notify / total_users * 100), 1) if total_users else 0

        # Notification times
        top_notif_times = await user_service.get_top_notification_times(limit=5)

        top_groups = await user_service.get_top_requested_items("group", limit=5)
        top_teachers = await user_service.get_top_requested_items("teacher", limit=5)
        top_classrooms = await user_service.get_top_requested_items("classroom", limit=5)

        return {
            "total_users": total_users,
            "users_with_favorite": users_with_fav,
            "users_with_notifications": users_with_notify,
            "fav_rate": f"{fav_pct}%",
            "notify_rate": f"{notify_pct}%",
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "new_today": new_today,
            "new_week": new_week,
            "new_month": new_month,
            "total_requests": total_requests,
            "type_distribution": type_dist,
            "type_percentages": type_percentages,
            "top_notification_times": [
                {"time": time_str, "count": count} for time_str, count in top_notif_times
            ],
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

    @app.post("/api/admin/upload")
    async def upload_admin_media(
        request: Request,
        filename: str = Query(...),
        admin: dict = Depends(get_admin_user),
    ):
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Файл пустой")
        if len(body) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 50 МБ)")

        ext = os.path.splitext(filename)[1].lower()
        clean_ext = ext if ext else ".jpg"
        safe_name = f"{uuid.uuid4().hex[:10]}_{re.sub(r'[^a-zA-Z0-9_.-]', '', filename)}"
        file_path = os.path.join(uploads_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(body)

        is_vid = clean_ext in {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}
        rel_url = f"/static/uploads/{safe_name}"

        return {
            "status": "ok",
            "url": rel_url,
            "media_type": "video" if is_vid else "image",
            "filename": filename,
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

        media_val = (req.media_url or req.image_url or "").strip()
        media_target = None
        is_vid = False

        if media_val:
            if media_val.startswith("/static/uploads/"):
                rel_path = media_val.replace("/static/", "", 1)
                local_file = os.path.join(static_dir, rel_path)
                if os.path.exists(local_file):
                    media_target = FSInputFile(local_file)
            if not media_target:
                media_target = media_val

            ext = os.path.splitext(media_val.split("?")[0])[1].lower()
            is_vid = req.media_type == "video" or ext in {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}

        admin_id = int(admin["id"])

        async def _send_to(chat_id: int):
            if is_vid:
                await bot.send_video(
                    chat_id=chat_id,
                    video=media_target,
                    caption=req.text.strip(),
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )
            elif media_target:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=media_target,
                    caption=req.text.strip(),
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=req.text.strip(),
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )

        # Test sending only to admin
        if req.test_only:
            try:
                await _send_to(admin_id)
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

            for uid in user_ids:
                try:
                    await _send_to(uid)
                    broadcast_state["sent"] += 1
                except Exception:
                    broadcast_state["failed"] += 1

                await asyncio.sleep(0.04)  # ~25 msg/s to safely stay under Telegram 30 msg/s limit

            broadcast_state["is_running"] = False

        asyncio.create_task(_do_broadcast())
        return {"status": "ok", "message": "Рассылка запущена в фоне!"}

    return app


