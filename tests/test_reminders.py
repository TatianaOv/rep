import logging

import pytest

from app.models import Lesson, Recipient
from app.reminders import _broadcast, _lesson_needs_start_reminder, _lesson_text


def test_school_lesson_does_not_need_a_start_reminder():
    assert _lesson_needs_start_reminder(Lesson(source="школа")) is False


def test_non_school_lesson_still_gets_a_start_reminder():
    assert _lesson_needs_start_reminder(Lesson(source="")) is True
    assert _lesson_needs_start_reminder(Lesson()) is True  # source unset -> normal behaviour


def test_lesson_text_shows_minutes_remaining():
    lesson = Lesson(subject="Математика", teacher="Мария", room="204")
    text = _lesson_text(lesson, 15)
    assert "Через 15 мин" in text
    assert "Математика" in text
    assert "Мария" in text
    assert "каб. 204" in text


def test_lesson_text_switches_to_in_progress_once_started():
    # Regression test: repeated lesson reminders used to always show the
    # original "через N мин" no matter how much time had actually passed,
    # so it kept saying "через 15 мин" even after the lesson had started.
    lesson = Lesson(subject="Физика")
    assert "Сейчас идёт" in _lesson_text(lesson, 0)
    assert "Сейчас идёт" in _lesson_text(lesson, -3)
    assert "через" not in _lesson_text(lesson, -3).lower()


@pytest.mark.asyncio
async def test_broadcast_skips_failing_recipient_without_aborting_others(caplog):
    # Regression test: a single recipient failing (e.g. they blocked the
    # bot) used to raise out of _broadcast and abort the rest of that
    # tick() — including reminders meant for everyone else.
    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
            if chat_id == 2:
                raise RuntimeError("bot was blocked by this user")
            sent.append(chat_id)

    recipients = [
        Recipient(telegram_chat_id=1),
        Recipient(telegram_chat_id=2),
        Recipient(telegram_chat_id=3),
    ]

    with caplog.at_level(logging.ERROR):
        await _broadcast(FakeBot(), recipients, "test message")

    assert sent == [1, 3]
    assert "Failed to send reminder" in caplog.text
