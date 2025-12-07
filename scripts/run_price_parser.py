import csv
import multiprocessing
import os
import sys
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from multiprocessing import Process

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from selenium import webdriver

from app.price_parsing_service import PriceParsingService
from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_price_repo import PostgresPriceRepository
from infrastructure.selen.hotel_gateway import SeleniumHotelGateway
from parser.funcs.common_funcs import create_browser_options

WORKER_COUNT = 4
CHUNK_DAYS = 4
MAX_ATTEMPTS = 3
CSV_ENCODING = "utf-8-sig"


def log_to_csv(csv_path, worker_id, attempt, start_date, days, status, message):
    """Append a single log line to the per-worker csv."""
    timestamp = datetime.now().isoformat()
    with open(csv_path, mode="a", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                timestamp,
                worker_id,
                attempt,
                start_date.isoformat(),
                days,
                status,
                message,
            ]
        )


class CsvPrintLogger:
    """Mirror stdout while appending each printed line to the CSV log."""

    def __init__(self, csv_path, worker_id, attempt, start_date, days, original_stdout):
        self.csv_path = csv_path
        self.worker_id = worker_id
        self.attempt = attempt
        self.start_date = start_date
        self.days = days
        self._buffer = ""
        self._original_stdout = original_stdout

    def write(self, data):
        self._original_stdout.write(data)
        self._original_stdout.flush()
        self._buffer += data
        self._flush_buffer_lines()

    def flush(self):
        self._original_stdout.flush()
        self._flush_buffer_lines(flush_remaining=True)

    def _flush_buffer_lines(self, flush_remaining=False):
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                log_to_csv(
                    self.csv_path,
                    self.worker_id,
                    self.attempt,
                    self.start_date,
                    self.days,
                    "print",
                    line,
                )
        if flush_remaining and self._buffer.strip():
            log_to_csv(
                self.csv_path,
                self.worker_id,
                self.attempt,
                self.start_date,
                self.days,
                "print",
                self._buffer.strip(),
            )
            self._buffer = ""


@contextmanager
def capture_prints_to_csv(csv_path, worker_id, attempt, start_date, days):
    """Redirect stdout to also log print lines into CSV."""
    original_stdout = sys.stdout
    logger = CsvPrintLogger(
        csv_path, worker_id, attempt, start_date, days, original_stdout
    )
    sys.stdout = logger
    try:
        yield
    finally:
        logger.flush()
        sys.stdout = original_stdout


def run_parser(worker_id, attempt, start_date, days, csv_path):
    """Run parsing for a date range; exceptions bubble up to allow retries."""
    start_str = start_date.isoformat()
    end_str = (start_date + timedelta(days=days - 1)).isoformat()
    with capture_prints_to_csv(csv_path, worker_id, attempt, start_date, days):
        def progress_callback(done, total):
            percent = int(done / total * 100)
            print(f"[parser-{worker_id}] progress {done}/{total} ({percent}%)")

        print(
            f"[parser-{worker_id}] attempt {attempt}: starting range {start_str} -> {end_str}"
        )
        log_to_csv(
            csv_path,
            worker_id,
            attempt,
            start_date,
            days,
            "start",
            f"starting range {start_str} -> {end_str}",
        )

        try:
            options = create_browser_options()
            with get_connection() as conn:
                repo = PostgresPriceRepository(conn)
                with webdriver.Chrome(options=options) as browser:
                    gateway = SeleniumHotelGateway(browser)
                    service = PriceParsingService(repo, gateway)
                    service.parse_period(start_date, days, progress_callback)

            print(
                f"[parser-{worker_id}] attempt {attempt}: finished range {start_str} -> {end_str}"
            )
            log_to_csv(
                csv_path,
                worker_id,
                attempt,
                start_date,
                days,
                "success",
                f"completed range {start_str} -> {end_str}",
            )
        except Exception:
            error_msg = traceback.format_exc()
            print(
                f"[parser-{worker_id}] attempt {attempt}: failed on range {start_str} -> {end_str}\n{error_msg}"
            )
            log_to_csv(
                csv_path,
                worker_id,
                attempt,
                start_date,
                days,
                "error",
                error_msg,
            )
            raise


def start_worker(worker_id, attempt, start_date, days, csv_path) -> Process:
    process = Process(
        target=run_parser, args=(worker_id, attempt, start_date, days, csv_path)
    )
    process.start()
    return process


def truncate_regular_prices():
    print("[trace] clearing regular_prices table before parsing")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE regular_prices;")
        conn.commit()
    print("[trace] regular_prices cleared")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    start_date = datetime.today().date()

    print("[trace] run_price_parser main start")
    print(
        f"[trace] parameters prepared start={start_date}, chunk_days={CHUNK_DAYS}, workers={WORKER_COUNT}"
    )

    truncate_regular_prices()

    chunks = []
    for idx in range(WORKER_COUNT):
        chunk_start = start_date + timedelta(days=idx * CHUNK_DAYS)
        chunks.append((idx + 1, chunk_start, CHUNK_DAYS))

    csv_paths = {}
    for worker_id, chunk_start, chunk_days in chunks:
        csv_path = os.path.join(ROOT, f"parser_worker_{worker_id}.csv")
        csv_paths[worker_id] = csv_path
        with open(csv_path, mode="w", newline="", encoding=CSV_ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(
                ["timestamp", "worker_id", "attempt", "start_date", "days", "status", "message"]
            )
        print(
            f"[trace] prepared csv log for worker {worker_id} at {csv_path} for range {chunk_start} -> {(chunk_start + timedelta(days=chunk_days - 1)).isoformat()}"
        )

    attempts = {worker_id: 1 for worker_id, _, _ in chunks}
    processes = {
        worker_id: start_worker(
            worker_id, attempts[worker_id], chunk_start, chunk_days, csv_paths[worker_id]
        )
        for worker_id, chunk_start, chunk_days in chunks
    }

    completed = []
    failed = []

    while processes:
        for worker_id, process in list(processes.items()):
            process.join()
            exit_code = process.exitcode
            if exit_code == 0:
                print(f"[trace] worker {worker_id} finished successfully")
                completed.append(worker_id)
                processes.pop(worker_id, None)
                continue

            attempts[worker_id] += 1
            if attempts[worker_id] > MAX_ATTEMPTS:
                print(
                    f"[trace] worker {worker_id} failed after {MAX_ATTEMPTS} attempts; skipping remaining retries"
                )
                failed.append(worker_id)
                processes.pop(worker_id, None)
                continue

            print(
                f"[trace] worker {worker_id} crashed with exit_code={exit_code}; restarting attempt {attempts[worker_id]}"
            )
            processes[worker_id] = start_worker(
                worker_id,
                attempts[worker_id],
                next(chunk_start for wid, chunk_start, _ in chunks if wid == worker_id),
                CHUNK_DAYS,
                csv_paths[worker_id],
            )

    print(f"[trace] all workers completed; success={completed}, failed={failed}")
