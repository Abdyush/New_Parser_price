import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram import Router
from dotenv import load_dotenv
import os

# Загружаем токен
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Импортируем твой router
from bot.handlers.registration import router as registration_router
from bot.handlers.profile import router as profile_router


async def on_startup(bot: Bot):
    # Устанавливаем команды меню бота
    commands = [
        BotCommand(command="start", description="Начать регистрацию"),
        BotCommand(command="profile", description="Показать профиль"),
    ]

    await bot.set_my_commands(commands)
    print("Bot commands installed")


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher(storage=MemoryStorage())

    # подключаем твои хендлеры
    dp.include_router(registration_router)
    dp.include_router(profile_router)

    # запускаем on_startup
    await on_startup(bot)

    print("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
