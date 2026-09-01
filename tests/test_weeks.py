import datetime as dt

from app.models import Lesson, PlannerSettings
from app.weeks import current_week_number, lesson_is_active_this_week

MONDAY_WEEK1 = dt.date(2026, 8, 10)
THURSDAY_WEEK1 = dt.date(2026, 8, 13)
MONDAY_WEEK2 = dt.date(2026, 8, 17)
THURSDAY_WEEK2 = dt.date(2026, 8, 20)
MONDAY_WEEK1_AGAIN = dt.date(2026, 8, 24)
MONDAY_BEFORE_ANCHOR = dt.date(2026, 8, 3)


def test_current_week_number_same_week_is_week_1():
    assert current_week_number(MONDAY_WEEK1, MONDAY_WEEK1) == 1
    assert current_week_number(THURSDAY_WEEK1, MONDAY_WEEK1) == 1


def test_current_week_number_alternates_weekly():
    assert current_week_number(MONDAY_WEEK2, MONDAY_WEEK1) == 2
    assert current_week_number(THURSDAY_WEEK2, MONDAY_WEEK1) == 2
    assert current_week_number(MONDAY_WEEK1_AGAIN, MONDAY_WEEK1) == 1


def test_current_week_number_before_anchor():
    assert current_week_number(MONDAY_BEFORE_ANCHOR, MONDAY_WEEK1) == 2


def test_lesson_active_ignored_when_biweekly_disabled():
    settings = PlannerSettings(biweekly_enabled=False)
    lesson = Lesson(week=1)
    assert lesson_is_active_this_week(lesson, settings, THURSDAY_WEEK2) is True


def test_lesson_active_every_week_when_week_is_zero():
    settings = PlannerSettings(biweekly_enabled=True, biweekly_anchor_date=MONDAY_WEEK1)
    lesson = Lesson(week=0)
    assert lesson_is_active_this_week(lesson, settings, THURSDAY_WEEK2) is True


def test_lesson_active_only_on_its_own_week():
    settings = PlannerSettings(biweekly_enabled=True, biweekly_anchor_date=MONDAY_WEEK1)
    week1_lesson = Lesson(week=1)
    week2_lesson = Lesson(week=2)

    assert lesson_is_active_this_week(week1_lesson, settings, MONDAY_WEEK1) is True
    assert lesson_is_active_this_week(week2_lesson, settings, MONDAY_WEEK1) is False
    assert lesson_is_active_this_week(week1_lesson, settings, MONDAY_WEEK2) is False
    assert lesson_is_active_this_week(week2_lesson, settings, MONDAY_WEEK2) is True


def test_lesson_active_falls_back_to_reference_date_without_anchor():
    # No anchor set: falls back to `today` as the anchor, so "today" is always week 1.
    settings = PlannerSettings(biweekly_enabled=True, biweekly_anchor_date=None)
    week1_lesson = Lesson(week=1)
    assert lesson_is_active_this_week(week1_lesson, settings, THURSDAY_WEEK2) is True
