from __future__ import annotations

import datetime as dt

from app.models import Lesson, PlannerSettings


def _week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def current_week_number(today: dt.date, anchor: dt.date) -> int:
    """1 or 2, alternating every 7 days starting from the Monday of `anchor`'s week."""
    weeks_diff = (_week_start(today) - _week_start(anchor)).days // 7
    return 1 if weeks_diff % 2 == 0 else 2


def lesson_is_active_this_week(lesson: Lesson, settings_row: PlannerSettings, today: dt.date) -> bool:
    if not settings_row.biweekly_enabled or lesson.week == 0:
        return True
    anchor = settings_row.biweekly_anchor_date or today
    return current_week_number(today, anchor) == lesson.week
