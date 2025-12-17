import asyncio
import os
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.notifications.notifier import send_notifications


async def _run():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await send_notifications(bot)
    finally:
        await bot.session.close()


def run():
    asyncio.run(_run())


if __name__ == "__main__":
    run()
