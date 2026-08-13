from zoneinfo import ZoneInfo


def test_common_timezones_load():
    # Regression test: python:3.12-slim has no OS-level tzdata, so
    # ZoneInfo() raised ZoneInfoNotFoundError for every timezone until
    # the `tzdata` package was added to requirements.txt. This fails
    # loudly if that dependency ever gets dropped again.
    for name in ("Europe/Moscow", "Europe/Belgrade", "UTC"):
        ZoneInfo(name)
