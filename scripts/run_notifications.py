import asyncio
import os
import sys
import time
import traceback
from uuid import uuid4

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.notifications.notifier import send_notifications
from infrastructure.system_event_logger import log_event


async def _run():
    start_ts = time.perf_counter()
    run_id = str(uuid4())
    log_event(
        level="INFO",
        source="notifications",
        event="started",
        run_id=run_id,
    )
    bot = None
    try:
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await send_notifications(bot)
        elapsed = time.perf_counter() - start_ts
        log_event(
            level="INFO",
            source="notifications",
            event="completed",
            run_id=run_id,
            duration_ms=int(elapsed * 1000),
        )
    except Exception:
        log_event(
            level="ERROR",
            source="notifications",
            event="failed",
            message=traceback.format_exc(),
            run_id=run_id,
            duration_ms=int((time.perf_counter() - start_ts) * 1000),
        )
        raise
    finally:
        if bot is not None:
            await bot.session.close()


def run():
    asyncio.run(_run())


if __name__ == "__main__":
    run()
