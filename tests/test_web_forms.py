import asyncio
import re

import pytest
from starlette.testclient import TestClient

from app.db import init_db
from app.web.server import create_app


def _csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf_token hidden field not found on page"
    return match.group(1)


@pytest.fixture(scope="module")
def client():
    asyncio.run(init_db())
    with TestClient(create_app(), base_url="http://testserver") as test_client:
        r = test_client.get("/login")
        token = _csrf_token(r.text)
        test_client.post("/login", data={"csrf_token": token, "username": "test", "password": "test-password-12345"})
        yield test_client


def test_valid_lesson_can_be_added(client):
    r = client.get("/schedule")
    token = _csrf_token(r.text)
    r = client.post(
        "/schedule/add",
        data={
            "csrf_token": token,
            "day_of_week": "0",
            "start_time": "09:00",
            "end_time": "09:45",
            "subject": "Настоящий урок",
            "room": "",
            "teacher": "",
            "link": "",
            "week": "0",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "Настоящий урок" in client.get("/schedule").text


def test_invalid_time_shows_friendly_error_instead_of_crashing(client):
    r = client.get("/schedule")
    token = _csrf_token(r.text)
    r = client.post(
        "/schedule/add",
        data={
            "csrf_token": token,
            "day_of_week": "0",
            "start_time": "not-a-time",
            "end_time": "",
            "subject": "Плохой урок",
            "room": "",
            "teacher": "",
            "link": "",
            "week": "0",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = client.get("/schedule").text
    assert "Проверьте время" in page
    assert "Плохой урок" not in page


def test_forged_csrf_token_is_rejected(client):
    r = client.post(
        "/schedule/add",
        data={
            "csrf_token": "forged-token",
            "day_of_week": "0",
            "start_time": "10:00",
            "end_time": "",
            "subject": "НЕ ДОЛЖНО ПОЯВИТЬСЯ",
            "room": "",
            "teacher": "",
            "link": "",
            "week": "0",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = client.get("/schedule").text
    assert "НЕ ДОЛЖНО ПОЯВИТЬСЯ" not in page
    assert "Сессия обновилась" in page


def test_invalid_date_in_homework_shows_friendly_error(client):
    r = client.get("/homework")
    token = _csrf_token(r.text)
    r = client.post(
        "/homework/add",
        data={
            "csrf_token": token,
            "subject": "Матем",
            "description": "desc",
            "due_date": "not-a-date",
            "due_time": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "Проверьте дату" in client.get("/homework").text
