import os
import sys
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.handlers.registration import router as registration_router
from bot.handlers.profile import router as profile_router
from bot.handlers import notifications as notifications_handlers
from bot.handlers.admin import router as admin_router


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запуск регистрации"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="send_notifications", description="Тестовая отправка уведомлений"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Bot commands installed")


def build_redis_storage() -> RedisStorage:
    """Создаёт RedisStorage из переменных окружения."""
    auth_part = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    url = f"redis://{auth_part}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    return RedisStorage.from_url(url, state_ttl=None, data_ttl=None)


async def main():
    storage = build_redis_storage()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    dp.include_router(registration_router)
    dp.include_router(profile_router)
    dp.include_router(notifications_handlers.router)
    dp.include_router(admin_router)

    await on_startup(bot)

    logger.info("Bot is running...")
    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()
        await storage.wait_closed()
        await bot.session.close()


run_bot = main


if __name__ == "__main__":
    asyncio.run(main())
