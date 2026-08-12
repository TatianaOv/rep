from __future__ import annotations

import datetime as dt

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select

from app.config import config
from app.constants import DAY_NAMES
from app.db import async_session
from app.formatting import format_homework, format_lessons
from app.models import Homework, Lesson, Recipient
from app.services import consume_link_code, find_recipient_by_chat_id

router = Router()

HELP_TEXT = "Команды:\n/today — расписание и ДЗ на сегодня\n/week — расписание на неделю\n/homework — список ДЗ"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        existing = await find_recipient_by_chat_id(session, message.chat.id)
        if existing:
            await message.answer(f"Привет! Бот уже подключён к этому чату 👋\n{HELP_TEXT}")
            return

        args = (message.text or "").split(maxsplit=1)
        code = args[1].strip() if len(args) > 1 else None

        if not code:
            await message.answer("Нужен код привязки. Спроси его у родителя и отправь команду:\n/start КОД")
            return

        link_code = await consume_link_code(session, code)
        if not link_code:
            await message.answer("Код неверен или уже использован. Попроси родителя выдать новый в веб-панели.")
            return

        recipient = Recipient(
            label=link_code.label,
            telegram_chat_id=message.chat.id,
            telegram_username=message.from_user.username if message.from_user else None,
        )
        session.add(recipient)
        await session.delete(link_code)
        await session.commit()
        await message.answer(f"Готово! Бот подключён 🎉\n\n{HELP_TEXT}")


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return

        today = dt.date.today()
        weekday = today.weekday()
        result = await session.execute(
            select(Lesson).where(Lesson.day_of_week == weekday, Lesson.active.is_(True)).order_by(Lesson.start_time)
        )
        lessons = result.scalars().all()
        result = await session.execute(
            select(Homework)
            .where(Homework.due_date == today, Homework.done.is_(False))
            .order_by(Homework.due_time)
        )
        hw = result.scalars().all()

        text = f"📅 {DAY_NAMES[weekday]}, {today.strftime('%d.%m')}\n\n{format_lessons(lessons)}"
        if hw:
            text += f"\n\n📚 ДЗ на сегодня:\n{format_homework(hw)}"
        await message.answer(text)


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return

        result = await session.execute(
            select(Lesson).where(Lesson.active.is_(True)).order_by(Lesson.day_of_week, Lesson.start_time)
        )
        lessons = result.scalars().all()
        by_day: dict[int, list[Lesson]] = {}
        for lesson in lessons:
            by_day.setdefault(lesson.day_of_week, []).append(lesson)

        if not by_day:
            await message.answer("Расписание пока не заполнено.")
            return

        parts = [f"{DAY_NAMES[day]}:\n{format_lessons(by_day[day])}" for day in range(7) if day in by_day]
        await message.answer("\n\n".join(parts))


@router.message(Command("homework"))
async def cmd_homework(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return

        today = dt.date.today()
        result = await session.execute(
            select(Homework)
            .where(Homework.done.is_(False), Homework.due_date >= today)
            .order_by(Homework.due_date)
        )
        hw = result.scalars().all()
        await message.answer(f"📚 Домашние задания:\n{format_homework(hw)}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
