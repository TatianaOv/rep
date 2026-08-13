from __future__ import annotations

import datetime as dt


class ValidationError(Exception):
    """Raised with a message safe to show directly to the parent in the web panel."""


def parse_time(value: str, field: str) -> dt.time:
    try:
        return dt.time.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"Проверьте время в поле «{field}» — похоже, оно указано неверно.") from None


def parse_optional_time(value: str, field: str) -> dt.time | None:
    value = value.strip()
    if not value:
        return None
    return parse_time(value, field)


def parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"Проверьте дату в поле «{field}» — похоже, она указана неверно.") from None


def parse_optional_date(value: str, field: str) -> dt.date | None:
    value = value.strip()
    if not value:
        return None
    return parse_date(value, field)
