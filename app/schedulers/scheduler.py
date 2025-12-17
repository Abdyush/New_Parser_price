import asyncio
import logging
from functools import partial

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scripts import run_price_parser, run_offers_parser, run_price_matching, run_notifications

logger = logging.getLogger(__name__)


async def _run_job(fn, name: str):
    """Run blocking job in a thread, log errors without stopping scheduler."""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, fn)
        logger.info("Job %s finished successfully", name)
    except Exception:
        logger.exception("Job %s failed", name)


async def _run_pipeline():
    """Run price parser -> offers parser -> matching -> notifications sequentially."""
    loop = asyncio.get_running_loop()
    steps = [
        (run_price_parser.run, "price_parser"),
        (run_offers_parser.run, "offers_parser"),
        (run_price_matching.run, "price_matching"),
        (run_notifications.run, "notifications"),
    ]

    for fn, name in steps:
        try:
            await loop.run_in_executor(None, fn)
            logger.info("Pipeline step %s finished successfully", name)
        except Exception:
            logger.exception("Pipeline step %s failed, aborting pipeline", name)
            return


def create_scheduler(timezone: str | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone)

    scheduler.add_job(
        _run_pipeline,
        trigger=CronTrigger(hour=11, minute=30),
        id="daily_pipeline",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    return scheduler
