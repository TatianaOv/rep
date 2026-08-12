from __future__ import annotations

import datetime as dt
import os
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.config import config
from app.constants import DAY_NAMES
from app.db import async_session
from app.models import Homework, Lesson
from app.services import get_or_create_settings, get_or_create_student

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
        if username == config.admin_username and password == config.admin_password:
            request.session["authed"] = True
            return RedirectResponse("/", status_code=303)
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
            student = await get_or_create_student(session)
            today = dt.date.today()
            weekday = today.weekday()
            result = await session.execute(
                select(Lesson)
                .where(Lesson.day_of_week == weekday, Lesson.active.is_(True))
                .order_by(Lesson.start_time)
            )
            today_lessons = result.scalars().all()
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
                "student": student,
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
        by_day: dict[int, list[Lesson]] = {i: [] for i in range(7)}
        for lesson in lessons:
            by_day[lesson.day_of_week].append(lesson)
        return templates.TemplateResponse(
            request, "schedule.html", {"by_day": by_day, "day_names": DAY_NAMES}
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

    # ---------- Homework ----------
    @app.get("/homework", response_class=HTMLResponse)
    async def homework_view(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            result = await session.execute(select(Homework).order_by(Homework.done, Homework.due_date))
            items = result.scalars().all()
        return templates.TemplateResponse(request, "homework.html", {"items": items})

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
        return templates.TemplateResponse(
            request, "settings.html", {"settings": settings_row, "student": student}
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
            await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/link_code")
    async def settings_link_code(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            settings_row = await get_or_create_settings(session)
            settings_row.link_code = secrets.token_hex(3)
            await session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/unlink")
    async def settings_unlink(request: Request):
        redirect = redirect_if_unauthed(request)
        if redirect:
            return redirect
        async with async_session() as session:
            student = await get_or_create_student(session)
            student.telegram_chat_id = None
            student.telegram_username = None
            student.linked_at = None
            await session.commit()
        return RedirectResponse("/settings", status_code=303)

    return app
