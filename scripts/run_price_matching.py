import os
import sys
import time
import traceback
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.matching.pricing_service import run_pricing
from infrastructure.system_event_logger import log_event


def run():
    start_ts = time.perf_counter()
    run_id = str(uuid4())
    log_event(
        level="INFO",
        source="price_matching",
        event="started",
        run_id=run_id,
    )
    try:
        run_pricing()
        elapsed = time.perf_counter() - start_ts
        log_event(
            level="INFO",
            source="price_matching",
            event="completed",
            run_id=run_id,
            duration_ms=int(elapsed * 1000),
        )
    except Exception:
        log_event(
            level="ERROR",
            source="price_matching",
            event="failed",
            message=traceback.format_exc(),
            run_id=run_id,
            duration_ms=int((time.perf_counter() - start_ts) * 1000),
        )
        raise


if __name__ == "__main__":
    run()
