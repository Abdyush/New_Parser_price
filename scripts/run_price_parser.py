import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datetime import datetime
from selenium import webdriver
from core.entities import RegularPrice
from app.price_parsing_service import PriceParsingService
from infrastructure.selen.hotel_gateway import SeleniumHotelGateway
from infrastructure.db.postgres_price_repo import PostgresPriceRepository
from infrastructure.db.common_db import get_connection
from parser.funcs.common_funcs import create_browser_options

if __name__ == "__main__":
    print("[trace] run_price_parser main start")
    start = datetime.today().date()
    days = 2
    print(f"[trace] parameters prepared start={start}, days={days}")

    options = create_browser_options()
    print("[trace] browser options created")

    with get_connection() as conn:
        print("[trace] database connection opened")
        repo = PostgresPriceRepository(conn)
        print("[trace] PostgresPriceRepository created")

        with webdriver.Chrome(options=options) as browser:
            print("[trace] Chrome webdriver started")
            gateway = SeleniumHotelGateway(browser)
            print("[trace] SeleniumHotelGateway created")

            service = PriceParsingService(repo, gateway)
            print("[trace] PriceParsingService created")

            service.parse_period(start, days)
            print("[trace] parse_period completed")

    print("Парсинг завершён успешно")
