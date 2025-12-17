import asyncio
import os

from dotenv import load_dotenv

from app.schedulers.scheduler import create_scheduler
from bot.bot import run_bot
from infrastructure.logging_config import setup_logging


async def main():
    load_dotenv()
    setup_logging()

    scheduler = create_scheduler(os.getenv("TZ"))
    scheduler.start()

    try:
        await run_bot()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
