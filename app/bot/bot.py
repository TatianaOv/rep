from __future__ import annotations

import datetime as dt
import random

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.ai_companion import get_ai_turn
from app.config import config
from app.constants import DAY_NAMES
from app.db import async_session
from app.formatting import format_homework, format_lessons
from app.keyboards import homework_done_keyboard
from app.models import Homework, Lesson, PlannerSettings, Recipient
from app.services import (
    add_ai_message,
    clear_ai_history,
    consume_link_code,
    find_recipient_by_chat_id,
    get_ai_history,
    get_or_create_settings,
    get_or_create_student,
)
from app.voice import transcribe_voice
from app.weeks import current_week_number, lesson_is_active_this_week

router = Router()

HELP_TEXT = (
    "Команды:\n/today — расписание и ДЗ на сегодня\n/week — расписание на неделю\n"
    "/homework — список ДЗ\n/reset — начать разговор с ботом заново"
)

BOT_COMMANDS = [
    BotCommand(command="today", description="Расписание и ДЗ на сегодня"),
    BotCommand(command="week", description="Расписание на неделю"),
    BotCommand(command="homework", description="Список домашних заданий"),
    BotCommand(command="reset", description="Начать разговор с ботом заново"),
    BotCommand(command="help", description="Список команд"),
]

CELEBRATIONS = [
    "Ты огонь! 🔥",
    "Красотка, домашка сделана! 🎉",
    "Ещё одна закрыта! 💪✨",
    "Красава! 🥳",
    "Учёба идёт отлично! 🌟",
    "Мозг прокачан! 🧠⚡",
]


async def _build_today(session, settings_row: PlannerSettings) -> tuple[str, InlineKeyboardMarkup | None]:
    today = dt.date.today()
    weekday = today.weekday()
    result = await session.execute(
        select(Lesson).where(Lesson.day_of_week == weekday, Lesson.active.is_(True)).order_by(Lesson.start_time)
    )
    lessons = [lesson for lesson in result.scalars().all() if lesson_is_active_this_week(lesson, settings_row, today)]
    result = await session.execute(
        select(Homework).where(Homework.due_date == today, Homework.done.is_(False)).order_by(Homework.due_time)
    )
    hw = result.scalars().all()

    text = f"📅 {DAY_NAMES[weekday]}, {today.strftime('%d.%m')}\n\n{format_lessons(lessons)}"
    if hw:
        text += f"\n\n📚 ДЗ на сегодня:\n\n{format_homework(hw)}"
    return text, homework_done_keyboard(hw)


async def _build_week(session, settings_row: PlannerSettings) -> str:
    today = dt.date.today()
    result = await session.execute(
        select(Lesson).where(Lesson.active.is_(True)).order_by(Lesson.day_of_week, Lesson.start_time)
    )
    lessons = [lesson for lesson in result.scalars().all() if lesson_is_active_this_week(lesson, settings_row, today)]
    by_day: dict[int, list[Lesson]] = {}
    for lesson in lessons:
        by_day.setdefault(lesson.day_of_week, []).append(lesson)

    if not by_day:
        return "Расписание пока не заполнено."

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
    return header + "\n\n".join(parts)


async def _build_homework(session) -> tuple[str, InlineKeyboardMarkup | None]:
    today = dt.date.today()
    result = await session.execute(
        select(Homework).where(Homework.done.is_(False), Homework.due_date >= today).order_by(Homework.due_date)
    )
    hw = result.scalars().all()
    return f"📚 Домашние задания:\n\n{format_homework(hw)}", homework_done_keyboard(hw)


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
        text, markup = await _build_today(session, settings_row)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return
        settings_row = await get_or_create_settings(session)
        text = await _build_week(session, settings_row)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("homework"))
async def cmd_homework(message: Message) -> None:
    async with async_session() as session:
        if not await find_recipient_by_chat_id(session, message.chat.id):
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return
        text, markup = await _build_homework(session)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


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


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    async with async_session() as session:
        recipient = await find_recipient_by_chat_id(session, message.chat.id)
        if not recipient:
            await message.answer("Бот не привязан к этому чату. Обратитесь к родителю.")
            return
        await clear_ai_history(session, recipient.id)
    await message.answer("Окей, начнём с чистого листа 🌱")


async def _companion_turn(message: Message, text: str) -> None:
    """Route a free-form (typed or transcribed) message: schedule/homework intents get
    exact data straight from the database; anything else goes to the private AI chat."""
    async with async_session() as session:
        recipient = await find_recipient_by_chat_id(session, message.chat.id)
        if not recipient:
            await message.answer("Нужен код привязки. Спроси его у родителя и отправь команду:\n/start КОД")
            return

        settings_row = await get_or_create_settings(session)
        if not settings_row.ai_companion_enabled or not config.anthropic_api_key:
            await message.answer(f"Не поняла 🙂\n\n{HELP_TEXT}")
            return

        student = await get_or_create_student(session)
        history = await get_ai_history(session, recipient.id)
        api_messages = [{"role": m.role, "content": m.content} for m in history] + [
            {"role": "user", "content": text}
        ]
        recipient_id = recipient.id
        recipient_label = recipient.label

    try:
        turn = await get_ai_turn(api_messages, student.name)
    except Exception:
        await message.answer("Что-то пошло не так, попробуй ещё раз чуть позже 🙏")
        return

    if turn.action in ("show_today", "show_week", "show_homework"):
        async with async_session() as session:
            settings_row = await get_or_create_settings(session)
            if turn.action == "show_today":
                reply_text, markup = await _build_today(session, settings_row)
            elif turn.action == "show_week":
                reply_text, markup = await _build_week(session, settings_row), None
            else:
                reply_text, markup = await _build_homework(session)
        await message.answer(reply_text, reply_markup=markup, parse_mode="HTML")
        return

    reply_text = turn.reply or "Извини, не получилось ответить 🙈"
    async with async_session() as session:
        await add_ai_message(session, recipient_id, "user", text)
        await add_ai_message(session, recipient_id, "assistant", reply_text)

    await message.answer(reply_text)

    if turn.concern:
        async with async_session() as session:
            result = await session.execute(select(Recipient).where(Recipient.notify_on_safety_concern.is_(True)))
            admins = list(result.scalars().all())
        who = recipient_label or "Кто-то"
        alert = (
            f"⚠️ Бот заметил тревожный сигнал в переписке с {who}:\n"
            f"{turn.concern_summary or 'нужно обратить внимание'}\n\nПожалуйста, поговорите."
        )
        for admin in admins:
            await message.bot.send_message(admin.telegram_chat_id, alert)


@router.message(F.text, ~F.text.startswith("/"))
async def handle_free_text(message: Message) -> None:
    await _companion_turn(message, message.text)


@router.message(F.voice)
async def handle_voice(message: Message) -> None:
    async with async_session() as session:
        recipient = await find_recipient_by_chat_id(session, message.chat.id)
        if not recipient:
            await message.answer("Нужен код привязки. Спроси его у родителя и отправь команду:\n/start КОД")
            return
        settings_row = await get_or_create_settings(session)

    if not settings_row.ai_companion_enabled or not config.anthropic_api_key:
        await message.answer(f"Не поняла 🙂\n\n{HELP_TEXT}")
        return

    if not config.openai_api_key:
        await message.answer("Голосовые сообщения пока не настроены — напиши мне текстом 🙂")
        return

    try:
        file_info = await message.bot.get_file(message.voice.file_id)
        buffer = await message.bot.download_file(file_info.file_path)
        text = await transcribe_voice(buffer.read())
    except Exception:
        await message.answer("Не получилось разобрать голосовое, попробуй написать текстом 🙏")
        return

    if not text:
        await message.answer("Не расслышала, можешь написать текстом? 🙂")
        return

    await message.answer(f"🎤 Услышала: «{text}»")
    await _companion_turn(message, text)


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
