import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from selenium import webdriver

from app.offers_parsing_service import OfferParsingService
from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_offers_repo import PostgresOfferRepository
from infrastructure.selen.offers_gateway import SeleniumOfferGateway
from parser.funcs.common_funcs import create_browser_options


def truncate_offers_tables(conn):
    print("[trace] clearing special_offers and special_offer_stay_periods")
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE special_offer_stay_periods, special_offers RESTART IDENTITY CASCADE;"
        )
    conn.commit()
    print("[trace] special_offers tables cleared")


if __name__ == "__main__":
    print("[trace] run_offer_parser main start")

    options = create_browser_options()

    with get_connection() as conn:
        truncate_offers_tables(conn)

        repo = PostgresOfferRepository(conn)
        print("[trace] PostgresOfferRepository created")

        with webdriver.Chrome(options=options) as browser:
            print("[trace] Chrome webdriver started")
            gateway = SeleniumOfferGateway(browser)
            print("[trace] SeleniumOfferGateway created")

            service = OfferParsingService(gateway, repo)
            print("[trace] OfferParsingService created")

            service.parse_offers()

    print("[trace] run_offer_parser main done")
