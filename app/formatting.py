from __future__ import annotations

from typing import Iterable

from app.models import Homework, Lesson


def format_lessons(lessons: Iterable[Lesson]) -> str:
    lessons = list(lessons)
    if not lessons:
        return "На сегодня уроков нет 🎉"
    lines = []
    for lesson in lessons:
        t = lesson.start_time.strftime("%H:%M")
        line = f"{t} — {lesson.subject}"
        if lesson.room:
            line += f" (каб. {lesson.room})"
        lines.append(line)
    return "\n".join(lines)


def format_homework(items: Iterable[Homework]) -> str:
    items = list(items)
    if not items:
        return "Домашних заданий нет 🎉"
    lines = []
    for hw in items:
        d = hw.due_date.strftime("%d.%m")
        lines.append(f"• {hw.subject} — {hw.description} (до {d})")
    return "\n".join(lines)
