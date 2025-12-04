from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from infrastructure.db import pricing_repository as repo
from infrastructure.db.common_db import get_connection

from .models import GuestRow, RoomRow, SpecialOfferData, StayPeriodData
from .pricing_logic import (
    build_priced_stays_for_guest,
    group_stays_into_periods,
    match_categories_for_guest,
)


def _process_guest(
    conn,
    guest: GuestRow,
    rooms: List[RoomRow],
    loyalty_discounts: Dict[str, int],
    offers: List[SpecialOfferData],
    stay_periods: Dict[UUID, List[StayPeriodData]],
    today: date,
) -> None:
    repo.delete_guest_prices(conn, guest.id)

    matched_categories = match_categories_for_guest(guest, rooms)
    if not matched_categories:
        print(f"No matching categories for guest {guest.id}")
        return

    regular_prices = repo.fetch_regular_prices(conn, matched_categories)
    if not regular_prices:
        print(f"No regular prices found for guest {guest.id}")
        return

    stays = build_priced_stays_for_guest(
        guest=guest,
        matched_prices=regular_prices,
        loyalty_discounts=loyalty_discounts,
        offers=offers,
        periods_map=stay_periods,
        today=today,
    )

    aggregated = group_stays_into_periods(stays)
    repo.save_guest_prices(conn, aggregated)

    print(f"Saved {len(aggregated)} rows for guest {guest.id}")


def run_pricing(today: Optional[date] = None) -> None:
    work_date = today or date.today()

    with get_connection() as conn:
        guests = repo.fetch_guests(conn)
        rooms = repo.fetch_rooms(conn)
        loyalty_discounts = repo.fetch_loyalty_discounts(conn)
        offers = repo.fetch_special_offers(conn)
        stay_periods = repo.fetch_stay_periods(conn)

        for guest in guests:
            print(f"Processing guest {guest.first_name} {guest.last_name} (id={guest.id})")
            _process_guest(
                conn=conn,
                guest=guest,
                rooms=rooms,
                loyalty_discounts=loyalty_discounts,
                offers=offers,
                stay_periods=stay_periods,
                today=work_date,
            )
