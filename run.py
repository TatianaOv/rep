from __future__ import annotations

import asyncio
import logging

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.bot import BOT_COMMANDS, create_bot_and_dispatcher
from app.config import config
from app.db import init_db
from app.reminders import tick
from app.web.server import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("planner")


async def main() -> None:
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN не задан. Заполните .env (см. .env.example).")

    await init_db()
    bot, dp = create_bot_and_dispatcher()
    await bot.set_my_commands(BOT_COMMANDS)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(tick, "interval", seconds=60, args=[bot])
    scheduler.start()

    web_app = create_app()
    uv_config = uvicorn.Config(web_app, host=config.web_host, port=config.web_port, log_level="info")
    server = uvicorn.Server(uv_config)

    logger.info("Запуск бота и веб-панели на %s:%s", config.web_host, config.web_port)
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
