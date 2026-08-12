from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.constants import DAY_NAMES
from app.db import async_session
from app.formatting import format_homework, format_lessons
from app.models import Homework, Lesson, ReminderLog
from app.services import get_or_create_settings, get_or_create_student


async def _already_sent(session, kind: str, ref_id: int | None, sent_date: dt.date) -> bool:
    result = await session.execute(
        select(ReminderLog).where(
            ReminderLog.kind == kind,
            ReminderLog.ref_id == ref_id,
            ReminderLog.sent_date == sent_date,
        )
    )
    return result.scalar_one_or_none() is not None


async def _log_sent(session, kind: str, ref_id: int | None, sent_date: dt.date) -> None:
    session.add(ReminderLog(kind=kind, ref_id=ref_id, sent_date=sent_date))
    try:
        await session.commit()
    except IntegrityError:
        # Another tick already logged this exact reminder — safe to ignore.
        await session.rollback()


async def tick(bot: Bot) -> None:
    """Runs once a minute; checks whether any reminder is due right now."""
    async with async_session() as session:
        settings_row = await get_or_create_settings(session)
        student = await get_or_create_student(session)
        if not student.telegram_chat_id:
            return

        tz = ZoneInfo(settings_row.timezone or "Europe/Moscow")
        now = dt.datetime.now(tz)
        today = now.date()
        hhmm = now.strftime("%H:%M")

        # --- Morning digest ---
        if settings_row.morning_digest_enabled and settings_row.morning_digest_time.strftime("%H:%M") == hhmm:
            if not await _already_sent(session, "morning_digest", None, today):
                weekday = today.weekday()
                result = await session.execute(
                    select(Lesson)
                    .where(Lesson.day_of_week == weekday, Lesson.active.is_(True))
                    .order_by(Lesson.start_time)
                )
                lessons = result.scalars().all()
                result = await session.execute(
                    select(Homework)
                    .where(Homework.due_date == today, Homework.done.is_(False))
                    .order_by(Homework.due_time)
                )
                hw = result.scalars().all()
                text = f"Доброе утро! 📅 {DAY_NAMES[weekday]}, {today.strftime('%d.%m')}\n\n{format_lessons(lessons)}"
                if hw:
                    text += f"\n\n📚 ДЗ на сегодня:\n{format_homework(hw)}"
                await bot.send_message(student.telegram_chat_id, text)
                await _log_sent(session, "morning_digest", None, today)

        # --- Reminder before each lesson ---
        if settings_row.lesson_reminder_minutes is not None:
            result = await session.execute(
                select(Lesson).where(Lesson.day_of_week == today.weekday(), Lesson.active.is_(True))
            )
            for lesson in result.scalars().all():
                reminder_dt = dt.datetime.combine(today, lesson.start_time, tzinfo=tz) - dt.timedelta(
                    minutes=settings_row.lesson_reminder_minutes
                )
                if reminder_dt.strftime("%H:%M") == hhmm and not await _already_sent(
                    session, "lesson", lesson.id, today
                ):
                    text = f"⏰ Через {settings_row.lesson_reminder_minutes} мин: {lesson.subject}"
                    if lesson.room:
                        text += f" (каб. {lesson.room})"
                    if lesson.link:
                        text += f"\n🔗 {lesson.link}"
                    await bot.send_message(student.telegram_chat_id, text)
                    await _log_sent(session, "lesson", lesson.id, today)

        # --- Homework reminders ---
        if settings_row.homework_reminder_time.strftime("%H:%M") == hhmm:
            result = await session.execute(
                select(Homework).where(Homework.due_date == today, Homework.done.is_(False))
            )
            for hw in result.scalars().all():
                if not await _already_sent(session, "homework_due", hw.id, today):
                    await bot.send_message(
                        student.telegram_chat_id,
                        f"📌 Сегодня срок сдачи: {hw.subject} — {hw.description}",
                    )
                    await _log_sent(session, "homework_due", hw.id, today)

            soon_date = today + dt.timedelta(days=settings_row.homework_reminder_days_before)
            result = await session.execute(
                select(Homework).where(Homework.due_date == soon_date, Homework.done.is_(False))
            )
            for hw in result.scalars().all():
                if not await _already_sent(session, "homework_due_soon", hw.id, today):
                    await bot.send_message(
                        student.telegram_chat_id,
                        f"📝 Скоро дедлайн ({soon_date.strftime('%d.%m')}): {hw.subject} — {hw.description}",
                    )
                    await _log_sent(session, "homework_due_soon", hw.id, today)
