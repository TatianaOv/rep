from __future__ import annotations

import datetime as dt
import random

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.config import config
from app.constants import DAY_NAMES
from app.db import async_session
from app.formatting import format_homework, format_lessons
from app.keyboards import homework_done_keyboard
from app.models import Homework, Lesson, Recipient
from app.services import consume_link_code, find_recipient_by_chat_id, get_or_create_settings
from app.weeks import current_week_number, lesson_is_active_this_week

router = Router()

HELP_TEXT = "Команды:\n/today — расписание и ДЗ на сегодня\n/week — расписание на неделю\n/homework — список ДЗ"

CELEBRATIONS = [
    "Ты огонь! 🔥",
    "Красотка, домашка сделана! 🎉",
    "Ещё одна закрыта! 💪✨",
    "Красава! 🥳",
    "Учёба идёт отлично! 🌟",
    "Мозг прокачан! 🧠⚡",
]


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

        settings_row = await get_or_create_settings(session)
        today = dt.date.today()
        weekday = today.weekday()
        result = await session.execute(
            select(Lesson).where(Lesson.day_of_week == weekday, Lesson.active.is_(True)).order_by(Lesson.start_time)
        )
        lessons = [
            lesson for lesson in result.scalars().all() if lesson_is_active_this_week(lesson, settings_row, today)
        ]
        result = await session.execute(
            select(Homework)
            .where(Homework.due_date == today, Homework.done.is_(False))
            .order_by(Homework.due_time)
        )
        hw = result.scalars().all()

        text = f"📅 {DAY_NAMES[weekday]}, {today.strftime('%d.%m')}\n\n{format_lessons(lessons)}"
        if hw:
            text += f"\n\n📚 ДЗ на сегодня:\n\n{format_homework(hw)}"
        await message.answer(text, reply_markup=homework_done_keyboard(hw), parse_mode="HTML")


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return

        settings_row = await get_or_create_settings(session)
        today = dt.date.today()
        result = await session.execute(
            select(Lesson).where(Lesson.active.is_(True)).order_by(Lesson.day_of_week, Lesson.start_time)
        )
        lessons = [
            lesson for lesson in result.scalars().all() if lesson_is_active_this_week(lesson, settings_row, today)
        ]
        by_day: dict[int, list[Lesson]] = {}
        for lesson in lessons:
            by_day.setdefault(lesson.day_of_week, []).append(lesson)

        if not by_day:
            await message.answer("Расписание пока не заполнено.")
            return

        header = ""
        if settings_row.biweekly_enabled:
            anchor = settings_row.biweekly_anchor_date or today
            header = f"(Неделя {current_week_number(today, anchor)})\n\n"

        today_weekday = today.weekday()
        parts = [
            f"{DAY_NAMES[day]}{' (СЕГОДНЯ)' if day == today_weekday else ''}:\n{format_lessons(by_day[day])}"
            for day in range(7)
            if day in by_day
        ]
        await message.answer(header + "\n\n".join(parts), parse_mode="HTML")


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
        await message.answer(
            f"📚 Домашние задания:\n\n{format_homework(hw)}",
            reply_markup=homework_done_keyboard(hw),
            parse_mode="HTML",
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(F.data.startswith("hwdone:"))
async def cb_homework_done(callback: CallbackQuery) -> None:
    hw_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        recipient = await find_recipient_by_chat_id(session, callback.message.chat.id)
        if not recipient:
            await callback.answer("Бот не привязан к этому чату.", show_alert=True)
            return

        hw = await session.get(Homework, hw_id)
        if not hw:
            await callback.answer("Задание не найдено.", show_alert=True)
            return

        already_done = hw.done
        hw.done = True
        await session.commit()

        notify_targets: list[Recipient] = []
        if not already_done:
            result = await session.execute(
                select(Recipient).where(
                    Recipient.notify_on_homework_done.is_(True),
                    Recipient.telegram_chat_id != callback.message.chat.id,
                )
            )
            notify_targets = list(result.scalars().all())
        who = recipient.label or "Кто-то"
        subject = hw.subject
        description = hw.description

    if callback.message.reply_markup:
        new_rows = [
            [btn for btn in row if btn.callback_data != callback.data]
            for row in callback.message.reply_markup.inline_keyboard
        ]
        new_rows = [row for row in new_rows if row]
        markup = InlineKeyboardMarkup(inline_keyboard=new_rows) if new_rows else None
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except TelegramBadRequest:
            pass

    if already_done:
        await callback.answer("Уже было отмечено выполненным ✅")
        return

    await callback.answer(random.choice(CELEBRATIONS))
    for target in notify_targets:
        await callback.bot.send_message(
            target.telegram_chat_id,
            f"✅ {who} отметил(а) домашку выполненной: {subject} — {description}",
        )


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
