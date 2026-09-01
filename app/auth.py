from __future__ import annotations

import time
from collections import defaultdict

import bcrypt

from app.config import config

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60

_password_hash = bcrypt.hashpw(config.admin_password.encode(), bcrypt.gensalt())
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def verify_password(password: str) -> bool:
    return bcrypt.checkpw(password.encode(), _password_hash)


def is_locked_out(client_ip: str) -> bool:
    now = time.time()
    recent = [t for t in _failed_attempts[client_ip] if now - t < LOGIN_LOCKOUT_SECONDS]
    _failed_attempts[client_ip] = recent
    return len(recent) >= MAX_LOGIN_ATTEMPTS


def record_failed_attempt(client_ip: str) -> None:
    _failed_attempts[client_ip].append(time.time())


def clear_failed_attempts(client_ip: str) -> None:
    _failed_attempts.pop(client_ip, None)
