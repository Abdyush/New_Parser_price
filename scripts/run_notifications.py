import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from app.notifications.notifier import send_notifications


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    sent = await send_notifications(bot)

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
