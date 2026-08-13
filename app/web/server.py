from __future__ import annotations

import datetime as dt
import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    clear_failed_attempts,
    is_locked_out,
    record_failed_attempt,
    verify_password,
)
from app.config import config
from app.constants import DAY_NAMES
from app.db import async_session
from app.models import Homework, LinkCode, Lesson, Recipient
from app.services import (
    create_link_code,
    get_or_create_settings,
    get_or_create_student,
    get_pending_link_codes,
    get_recipients,
)
from app.weeks import current_week_number, lesson_is_active_this_week

BASE_DIR = os.path.dirname(__file__)


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=config.session_secret)
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

    def redirect_if_unauthed(request: Request):
        if not request.session.get("authed"):
            return RedirectResponse("/login", status_code=303)
        return None

    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if request.session.get("authed"):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login")
    async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
        client_ip = request.client.host if request.client else "unknown"

        if is_locked_out(client_ip):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Слишком много неудачных попыток входа. Попробуйте снова через 15 минут."},
                status_code=429,
            )

        if username == config.admin_username and verify_password(password):
            clear_failed_attempts(client_ip)
            request.session["authed"] = True
            return RedirectResponse("/", status_code=303)

        record_failed_attempt(client_ip)
        return templates.TemplateResponse(
            request, "login.html", {"error": "Неверный логин или пароль"}, status_code=401
        )

    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            recipients = await get_recipients(session)
            settings_row = await get_or_create_settings(session)
            today = dt.date.today()
            weekday = today.weekday()
            result = await session.execute(
                select(Lesson)
                .where(Lesson.day_of_week == weekday, Lesson.active.is_(True))
                .order_by(Lesson.start_time)
            )
            today_lessons = [
                lesson for lesson in result.scalars().all() if lesson_is_active_this_week(lesson, settings_row, today)
            ]
            result = await session.execute(
                select(Homework)
                .where(Homework.done.is_(False), Homework.due_date >= today)
                .order_by(Homework.due_date)
                .limit(10)
            )
            upcoming_hw = result.scalars().all()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "recipients": recipients,
                "today_name": DAY_NAMES[weekday],
                "today_lessons": today_lessons,
                "upcoming_hw": upcoming_hw,
            },
        )

    # ---------- Schedule ----------
    @app.get("/schedule", response_class=HTMLResponse)
    async def schedule_view(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            result = await session.execute(select(Lesson).order_by(Lesson.day_of_week, Lesson.start_time))
            lessons = result.scalars().all()
            settings_row = await get_or_create_settings(session)
        by_day: dict[int, list[Lesson]] = {i: [] for i in range(7)}
        for lesson in lessons:
            by_day[lesson.day_of_week].append(lesson)
        today = dt.date.today()
        current_week = None
        if settings_row.biweekly_enabled:
            anchor = settings_row.biweekly_anchor_date or today
            current_week = current_week_number(today, anchor)
        return templates.TemplateResponse(
            request,
            "schedule.html",
            {
                "by_day": by_day,
                "day_names": DAY_NAMES,
                "today_weekday": today.weekday(),
                "biweekly_enabled": settings_row.biweekly_enabled,
                "current_week": current_week,
            },
        )

    @app.post("/schedule/add")
    async def schedule_add(
        request: Request,
        day_of_week: int = Form(...),
        start_time: str = Form(...),
        end_time: str = Form(""),
        subject: str = Form(...),
        room: str = Form(""),
        teacher: str = Form(""),
        link: str = Form(""),
        week: int = Form(0),
    ):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            lesson = Lesson(
                day_of_week=day_of_week,
                start_time=dt.time.fromisoformat(start_time),
                end_time=dt.time.fromisoformat(end_time) if end_time else None,
                subject=subject.strip(),
                room=room.strip() or None,
                teacher=teacher.strip() or None,
                link=link.strip() or None,
                week=week,
            )
            session.add(lesson)
            await session.commit()
        return RedirectResponse("/schedule", status_code=303)

    @app.get("/schedule/{lesson_id}/edit", response_class=HTMLResponse)
    async def schedule_edit_view(request: Request, lesson_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            lesson = await session.get(Lesson, lesson_id)
            if not lesson:
                return RedirectResponse("/schedule", status_code=303)
        return templates.TemplateResponse(
            request, "schedule_edit.html", {"lesson": lesson, "day_names": DAY_NAMES}
        )

    @app.post("/schedule/{lesson_id}/edit")
    async def schedule_edit_submit(
        request: Request,
        lesson_id: int,
        day_of_week: int = Form(...),
        start_time: str = Form(...),
        end_time: str = Form(""),
        subject: str = Form(...),
        room: str = Form(""),
        teacher: str = Form(""),
        link: str = Form(""),
        week: int = Form(0),
    ):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            lesson = await session.get(Lesson, lesson_id)
            if lesson:
                lesson.day_of_week = day_of_week
                lesson.start_time = dt.time.fromisoformat(start_time)
                lesson.end_time = dt.time.fromisoformat(end_time) if end_time else None
                lesson.subject = subject.strip()
                lesson.room = room.strip() or None
                lesson.teacher = teacher.strip() or None
                lesson.link = link.strip() or None
                lesson.week = week
                await session.commit()
        return RedirectResponse("/schedule", status_code=303)

    @app.post("/schedule/{lesson_id}/delete")
    async def schedule_delete(request: Request, lesson_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            lesson = await session.get(Lesson, lesson_id)
            if lesson:
                await session.delete(lesson)
                await session.commit()
        return RedirectResponse("/schedule", status_code=303)

    @app.post("/schedule/{lesson_id}/copy")
    async def schedule_copy(request: Request, lesson_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            lesson = await session.get(Lesson, lesson_id)
            if lesson:
                copy = Lesson(
                    day_of_week=lesson.day_of_week,
                    start_time=lesson.start_time,
                    end_time=lesson.end_time,
                    subject=lesson.subject,
                    room=lesson.room,
                    teacher=lesson.teacher,
                    link=lesson.link,
                    week=lesson.week,
                    active=lesson.active,
                )
                session.add(copy)
                await session.commit()
        return RedirectResponse("/schedule", status_code=303)

    # ---------- Homework ----------
    @app.get("/homework", response_class=HTMLResponse)
    async def homework_view(request: Request, copy_from: int | None = None):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            result = await session.execute(select(Homework).order_by(Homework.done, Homework.due_date))
            items = result.scalars().all()
            copy_source = await session.get(Homework, copy_from) if copy_from else None
        return templates.TemplateResponse(
            request, "homework.html", {"items": items, "copy_source": copy_source}
        )

    @app.post("/homework/add")
    async def homework_add(
        request: Request,
        subject: str = Form(...),
        description: str = Form(...),
        due_date: str = Form(...),
        due_time: str = Form(""),
    ):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            hw = Homework(
                subject=subject.strip(),
                description=description.strip(),
                due_date=dt.date.fromisoformat(due_date),
                due_time=dt.time.fromisoformat(due_time) if due_time else None,
            )
            session.add(hw)
            await session.commit()
        return RedirectResponse("/homework", status_code=303)

    @app.post("/homework/{hw_id}/toggle_done")
    async def homework_toggle(request: Request, hw_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            hw = await session.get(Homework, hw_id)
            if hw:
                hw.done = not hw.done
                await session.commit()
        return RedirectResponse("/homework", status_code=303)

    @app.post("/homework/{hw_id}/delete")
    async def homework_delete(request: Request, hw_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            hw = await session.get(Homework, hw_id)
            if hw:
                await session.delete(hw)
                await session.commit()
        return RedirectResponse("/homework", status_code=303)

    # ---------- Settings ----------
    @app.get("/settings", response_class=HTMLResponse)
    async def settings_view(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            settings_row = await get_or_create_settings(session)
            student = await get_or_create_student(session)
            recipients = await get_recipients(session)
            pending_codes = await get_pending_link_codes(session)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "settings": settings_row,
                "student": student,
                "recipients": recipients,
                "pending_codes": pending_codes,
                "ai_api_key_configured": bool(config.anthropic_api_key),
                "voice_api_key_configured": bool(config.groq_api_key),
            },
        )

    @app.post("/settings/update")
    async def settings_update(
        request: Request,
        student_name: str = Form(...),
        timezone: str = Form(...),
        morning_digest_enabled: str = Form(""),
        morning_digest_time: str = Form(...),
        lesson_reminder_minutes: str = Form(""),
        homework_reminder_time: str = Form(...),
        homework_reminder_days_before: int = Form(...),
        biweekly_enabled: str = Form(""),
        biweekly_anchor_date: str = Form(""),
        ai_companion_enabled: str = Form(""),
        lesson_reminder_repeat_enabled: str = Form(""),
        lesson_reminder_repeat_minutes: int = Form(5),
    ):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            settings_row = await get_or_create_settings(session)
            student = await get_or_create_student(session)
            student.name = student_name.strip() or student.name
            settings_row.timezone = timezone.strip() or "Europe/Moscow"
            settings_row.morning_digest_enabled = bool(morning_digest_enabled)
            settings_row.morning_digest_time = dt.time.fromisoformat(morning_digest_time)
            settings_row.lesson_reminder_minutes = (
                int(lesson_reminder_minutes) if lesson_reminder_minutes.strip() else None
            )
            settings_row.homework_reminder_time = dt.time.fromisoformat(homework_reminder_time)
            settings_row.homework_reminder_days_before = homework_reminder_days_before
            settings_row.biweekly_enabled = bool(biweekly_enabled)
            settings_row.biweekly_anchor_date = (
                dt.date.fromisoformat(biweekly_anchor_date) if biweekly_anchor_date.strip() else None
            )
            settings_row.ai_companion_enabled = bool(ai_companion_enabled)
            settings_row.lesson_reminder_repeat_enabled = bool(lesson_reminder_repeat_enabled)
            settings_row.lesson_reminder_repeat_minutes = max(1, lesson_reminder_repeat_minutes)
            await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/link_code")
    async def settings_link_code(request: Request, label: str = Form("")):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            await create_link_code(session, label)
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/link_codes/{code_id}/delete")
    async def settings_link_code_cancel(request: Request, code_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            link_code = await session.get(LinkCode, code_id)
            if link_code:
                await session.delete(link_code)
                await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/recipients/{recipient_id}/delete")
    async def settings_recipient_delete(request: Request, recipient_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            recipient = await session.get(Recipient, recipient_id)
            if recipient:
                await session.delete(recipient)
                await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/recipients/{recipient_id}/toggle_notify")
    async def settings_recipient_toggle_notify(request: Request, recipient_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            recipient = await session.get(Recipient, recipient_id)
            if recipient:
                recipient.notify_on_homework_done = not recipient.notify_on_homework_done
                await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/recipients/{recipient_id}/toggle_safety")
    async def settings_recipient_toggle_safety(request: Request, recipient_id: int):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            recipient = await session.get(Recipient, recipient_id)
            if recipient:
                recipient.notify_on_safety_concern = not recipient.notify_on_safety_concern
                await session.commit()
        return RedirectResponse("/settings", status_code=303)

    return app
