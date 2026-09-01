from __future__ import annotations

import html
from typing import Iterable

from app.constants import subject_marker
from app.models import Homework, Lesson


def format_lessons(lessons: Iterable[Lesson]) -> str:
    lessons = list(lessons)
    if not lessons:
        return "На сегодня уроков нет 🎉"
    lines = []
    for lesson in lessons:
        t = lesson.start_time.strftime("%H:%M")
        line = f"{t} — {subject_marker(lesson.subject)}{html.escape(lesson.subject)}"
        if lesson.teacher:
            line += f", {html.escape(lesson.teacher)}"
        if lesson.room:
            line += f" (каб. {html.escape(lesson.room)})"
        if lesson.link:
            line += f"\n🔗 {html.escape(lesson.link)}"
        lines.append(line)
    return "\n".join(lines)


def format_homework(items: Iterable[Homework]) -> str:
    items = list(items)
    if not items:
        return "Домашних заданий нет 🎉"
    lines = []
    for hw in items:
        d = hw.due_date.strftime("%d.%m")
        subject = html.escape(hw.subject)
        description = html.escape(hw.description)
        lines.append(f"• {subject_marker(hw.subject)}<b>{subject}</b> — {description} (до {d})")
    return "\n\n".join(lines)
