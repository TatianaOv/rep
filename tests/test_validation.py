import datetime as dt

import pytest

from app.validation import ValidationError, parse_date, parse_optional_date, parse_optional_time, parse_time


def test_parse_time_valid():
    assert parse_time("09:30", "Начало") == dt.time(9, 30)


def test_parse_time_invalid_raises_friendly_error():
    with pytest.raises(ValidationError, match="Начало"):
        parse_time("not-a-time", "Начало")


def test_parse_optional_time_empty_is_none():
    assert parse_optional_time("", "Конец") is None
    assert parse_optional_time("   ", "Конец") is None


def test_parse_optional_time_blank_but_present_still_validates():
    with pytest.raises(ValidationError):
        parse_optional_time("25:99", "Конец")


def test_parse_date_valid():
    assert parse_date("2026-08-13", "Срок сдачи") == dt.date(2026, 8, 13)


def test_parse_date_invalid_raises_friendly_error():
    with pytest.raises(ValidationError, match="Срок сдачи"):
        parse_date("13/08/2026", "Срок сдачи")


def test_parse_optional_date_empty_is_none():
    assert parse_optional_date("", "Начало Недели 1") is None
