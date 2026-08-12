from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.constants import DAY_NAMES
from app.db import async_session
from app.formatting import format_homework, format_lessons
from app.keyboards import homework_done_keyboard, lesson_ack_keyboard
from app.models import Homework, Lesson, Recipient, ReminderLog
from app.services import get_or_create_lesson_ping, get_or_create_settings, get_recipients
from app.weeks import lesson_is_active_this_week


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


async def _broadcast(
    bot: Bot,
    recipients: list[Recipient],
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    for recipient in recipients:
        await bot.send_message(recipient.telegram_chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)


def _lesson_text(lesson: Lesson, minutes: int) -> str:
    text = f"⏰ Через {minutes} мин: {lesson.subject}"
    if lesson.teacher:
        text += f", {lesson.teacher}"
    if lesson.room:
        text += f" (каб. {lesson.room})"
    if lesson.link:
        text += f"\n🔗 {lesson.link}"
    return text


async def tick(bot: Bot) -> None:
    """Runs once a minute; checks whether any reminder is due right now."""
    async with async_session() as session:
        settings_row = await get_or_create_settings(session)
        recipients = await get_recipients(session)
        if not recipients:
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
                lessons = [
                    lesson
                    for lesson in result.scalars().all()
                    if lesson_is_active_this_week(lesson, settings_row, today)
                ]
                result = await session.execute(
                    select(Homework)
                    .where(Homework.due_date == today, Homework.done.is_(False))
                    .order_by(Homework.due_time)
                )
                hw = result.scalars().all()
                text = f"Доброе утро! 📅 {DAY_NAMES[weekday]}, {today.strftime('%d.%m')}\n\n{format_lessons(lessons)}"
                if hw:
                    text += f"\n\n📚 ДЗ на сегодня:\n\n{format_homework(hw)}"
                await _broadcast(bot, recipients, text, homework_done_keyboard(hw), parse_mode="HTML")
                await _log_sent(session, "morning_digest", None, today)

        # --- Reminder before each lesson ---
        if settings_row.lesson_reminder_minutes is not None:
            result = await session.execute(
                select(Lesson).where(Lesson.day_of_week == today.weekday(), Lesson.active.is_(True))
            )
            for lesson in result.scalars().all():
                if not lesson_is_active_this_week(lesson, settings_row, today):
                    continue
                reminder_dt = dt.datetime.combine(today, lesson.start_time, tzinfo=tz) - dt.timedelta(
                    minutes=settings_row.lesson_reminder_minutes
                )

                if not settings_row.lesson_reminder_repeat_enabled:
                    if reminder_dt.strftime("%H:%M") == hhmm and not await _already_sent(
                        session, "lesson", lesson.id, today
                    ):
                        await _broadcast(bot, recipients, _lesson_text(lesson, settings_row.lesson_reminder_minutes))
                        await _log_sent(session, "lesson", lesson.id, today)
                    continue

                # Repeat mode: nudge every N minutes from reminder_dt until acknowledged,
                # giving up once the lesson's window (end_time, or +1h fallback) has passed.
                if now < reminder_dt:
                    continue
                window_end = (
                    dt.datetime.combine(today, lesson.end_time, tzinfo=tz)
                    if lesson.end_time
                    else reminder_dt + dt.timedelta(hours=1)
                )
                if now > window_end:
                    continue

                ping = await get_or_create_lesson_ping(session, lesson.id, today)
                if ping.acknowledged_at:
                    continue
                now_naive = now.replace(tzinfo=None)
                if ping.last_sent_at is not None:
                    elapsed_minutes = (now_naive - ping.last_sent_at).total_seconds() / 60
                    if elapsed_minutes < settings_row.lesson_reminder_repeat_minutes:
                        continue

                await _broadcast(
                    bot,
                    recipients,
                    _lesson_text(lesson, settings_row.lesson_reminder_minutes),
                    lesson_ack_keyboard(lesson.id),
                )
                ping.last_sent_at = now_naive
                await session.commit()

        # --- Homework reminders ---
        if settings_row.homework_reminder_time.strftime("%H:%M") == hhmm:
            result = await session.execute(
                select(Homework).where(Homework.due_date == today, Homework.done.is_(False))
            )
            for hw in result.scalars().all():
                if not await _already_sent(session, "homework_due", hw.id, today):
                    await _broadcast(
                        bot,
                        recipients,
                        f"📌 Сегодня срок сдачи: {hw.subject} — {hw.description}",
                        homework_done_keyboard([hw]),
                    )
                    await _log_sent(session, "homework_due", hw.id, today)

            soon_date = today + dt.timedelta(days=settings_row.homework_reminder_days_before)
            result = await session.execute(
                select(Homework).where(Homework.due_date == soon_date, Homework.done.is_(False))
            )
            for hw in result.scalars().all():
                if not await _already_sent(session, "homework_due_soon", hw.id, today):
                    await _broadcast(
                        bot,
                        recipients,
                        f"📝 Скоро дедлайн ({soon_date.strftime('%d.%m')}): {hw.subject} — {hw.description}",
                        homework_done_keyboard([hw]),
                    )
                    await _log_sent(session, "homework_due_soon", hw.id, today)
