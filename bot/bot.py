import os
import sys
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.handlers.registration import router as registration_router
from bot.handlers.profile import router as profile_router
from bot.handlers import notifications as notifications_handlers


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")


async def on_startup(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запуск регистрации"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="send_notifications", description="Тестовая отправка уведомлений"),
    ]

    await bot.set_my_commands(commands)
    print("Bot commands installed")


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(registration_router)
    dp.include_router(profile_router)
    dp.include_router(notifications_handlers.router)

    await on_startup(bot)

    print("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
