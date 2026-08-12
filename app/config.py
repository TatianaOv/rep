from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    bot_token: str = os.environ.get("BOT_TOKEN", "")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
    timezone: str = os.environ.get("TIMEZONE", "Europe/Moscow")
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "changeme")
    session_secret: str = os.environ.get("SESSION_SECRET_KEY", "insecure-dev-secret-change-me")
    web_host: str = os.environ.get("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.environ.get("WEB_PORT", "8000"))
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")


config = AppConfig()
