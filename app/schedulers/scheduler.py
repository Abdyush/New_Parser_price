import asyncio
import logging
import time
from uuid import uuid4
from functools import partial

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scripts import run_price_parser, run_offers_parser, run_price_matching, run_notifications
from infrastructure.system_event_logger import log_event

logger = logging.getLogger(__name__)


async def _run_job(fn, name: str):
    """Run blocking job in a thread, log errors without stopping scheduler."""
    loop = asyncio.get_running_loop()
    run_id = str(uuid4())
    started = time.perf_counter()
    log_event(
        level="INFO",
        source="scheduler",
        event="job_started",
        message=f"job={name}",
        meta={"job": name},
        run_id=run_id,
    )
    try:
        await loop.run_in_executor(None, fn)
        logger.info("Job %s finished successfully", name)
        log_event(
            level="INFO",
            source="scheduler",
            event="job_completed",
            message=f"job={name}",
            meta={"job": name},
            run_id=run_id,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception:
        logger.exception("Job %s failed", name)
        log_event(
            level="ERROR",
            source="scheduler",
            event="job_failed",
            message=f"job={name}",
            meta={"job": name},
            run_id=run_id,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


async def _run_pipeline():
    """Run price parser -> offers parser -> matching -> notifications sequentially."""
    loop = asyncio.get_running_loop()
    run_id = str(uuid4())
    pipeline_started = time.perf_counter()
    log_event(
        level="INFO",
        source="scheduler",
        event="pipeline_started",
        message="daily_pipeline",
        run_id=run_id,
    )
    steps = [
        (run_price_parser.run, "price_parser"),
        (run_offers_parser.run, "offers_parser"),
        (run_price_matching.run, "price_matching"),
        (run_notifications.run, "notifications"),
    ]

    for fn, name in steps:
        try:
            step_started = time.perf_counter()
            log_event(
                level="INFO",
                source="scheduler",
                event="pipeline_step_started",
                message=name,
                meta={"step": name},
                run_id=run_id,
            )
            await loop.run_in_executor(None, fn)
            logger.info("Pipeline step %s finished successfully", name)
            log_event(
                level="INFO",
                source="scheduler",
                event="pipeline_step_completed",
                message=name,
                meta={"step": name},
                run_id=run_id,
                duration_ms=int((time.perf_counter() - step_started) * 1000),
            )
        except Exception:
            logger.exception("Pipeline step %s failed, aborting pipeline", name)
            log_event(
                level="ERROR",
                source="scheduler",
                event="pipeline_step_failed",
                message=name,
                meta={"step": name},
                run_id=run_id,
                duration_ms=int((time.perf_counter() - step_started) * 1000),
            )
            log_event(
                level="ERROR",
                source="scheduler",
                event="pipeline_aborted",
                message=name,
                meta={"failed_step": name},
                run_id=run_id,
                duration_ms=int((time.perf_counter() - pipeline_started) * 1000),
            )
            return

    log_event(
        level="INFO",
        source="scheduler",
        event="pipeline_completed",
        message="daily_pipeline",
        run_id=run_id,
        duration_ms=int((time.perf_counter() - pipeline_started) * 1000),
    )


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
