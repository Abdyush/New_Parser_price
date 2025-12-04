from datetime import datetime
from typing import Dict, List
from uuid import UUID

from psycopg2.extensions import connection

from core.entities import RegularPrice
from app.matching.models import (
    AggregatedRow,
    GuestRow,
    RoomRow,
    SpecialOfferData,
    StayPeriodData,
)


def fetch_guests(conn: connection) -> List[GuestRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                id, first_name, last_name, adults, teens, infant, preferred_categories, loyalty_status
            FROM guest_details
            """
        )
        rows = cur.fetchall()

    guests: List[GuestRow] = []
    for r in rows:
        guests.append(
            GuestRow(
                id=r[0],
                first_name=r[1],
                last_name=r[2],
                adults=r[3],
                teens=r[4],
                infant=r[5],
                preferred_categories=r[6],
                loyalty_status=r[7],
            )
        )
    return guests


def fetch_rooms(conn: connection) -> List[RoomRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                id, room_category, number_of_main_beds
            FROM room_characteristics
            """
        )
        rows = cur.fetchall()

    rooms: List[RoomRow] = []
    for r in rows:
        rooms.append(
            RoomRow(
                id=r[0],
                category_name=r[1],
                number_of_main_beds=r[2],
            )
        )
    return rooms


def fetch_loyalty_discounts(conn: connection) -> Dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT level, discount_percent
            FROM loyalty_discounts
            """
        )
        rows = cur.fetchall()

    result: Dict[str, int] = {}
    for level, percent in rows:
        if level:
            result[level.strip().lower()] = int(percent)
    return result


def fetch_special_offers(conn: connection) -> List[SpecialOfferData]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, categories, formula, loyalty_compatible, booking_start, booking_end
            FROM special_offers
            """
        )
        rows = cur.fetchall()

    offers: List[SpecialOfferData] = []
    for r in rows:
        offer_id, categories, formula, compatible, b_start, b_end = r
        offers.append(
            SpecialOfferData(
                id=offer_id,
                categories=categories or [],
                formula=formula,
                loyalty_compatible=bool(compatible),
                booking_start=b_start,
                booking_end=b_end,
            )
        )
    return offers


def fetch_stay_periods(conn: connection) -> Dict[UUID, List[StayPeriodData]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT offer_id, stay_start, stay_end
            FROM special_offer_stay_periods
            """
        )
        rows = cur.fetchall()

    result: Dict[UUID, List[StayPeriodData]] = {}
    for offer_id, s_start, s_end in rows:
        sp = StayPeriodData(
            offer_id=offer_id,
            stay_start=s_start,
            stay_end=s_end,
        )
        result.setdefault(offer_id, []).append(sp)
    return result


def fetch_regular_prices(conn: connection, matched_categories: List[str]) -> List[RegularPrice]:
    if not matched_categories:
        return []

    like_patterns = [f"%{cat}%" for cat in matched_categories]
    where_clauses = " OR ".join(["room_category ILIKE %s" for _ in like_patterns])

    query = f"""
        SELECT 
            room_category,
            date,
            only_breakfast,
            full_pansion,
            is_last_room
        FROM regular_prices
        WHERE {where_clauses}
        ORDER BY room_category, date;
    """

    with conn.cursor() as cursor:
        cursor.execute(query, like_patterns)
        rows = cursor.fetchall()

    results: List[RegularPrice] = []

    for row in rows:
        category, dt, ob, fp, last_room = row

        rp = RegularPrice(
            category=category,
            date=dt,
            only_breakfast=ob,
            full_pansion=fp,
            is_last_room=last_room
        )
        results.append(rp)

    return results


def delete_guest_prices(conn: connection, guest_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM guest_prices WHERE guest_id = %s", (guest_id,))
    conn.commit()


def save_guest_prices(conn: connection, rows: List[AggregatedRow]) -> None:
    if not rows:
        return

    insert_sql = """
        INSERT INTO guest_prices (
            guest_id,
            category,
            period,
            regular_breakfast_price,
            new_breakfast_price,
            regular_full_pansion_price,
            new_full_pansion_price,
            applied_special_offer,
            applied_loyalty,
            formula_used,
            is_last_room,
            created_at
        )
        VALUES (
            %(guest_id)s,
            %(category)s,
            %(period)s,
            %(regular_breakfast_price)s,
            %(new_breakfast_price)s,
            %(regular_full_pansion_price)s,
            %(new_full_pansion_price)s,
            %(applied_special_offer)s,
            %(applied_loyalty)s,
            %(formula_used)s,
            %(is_last_room)s,
            %(created_at)s
        )
    """
    now = datetime.now()
    data = []
    for r in rows:
        data.append(
            {
                "guest_id": r.guest_id,
                "category": r.category,
                "period": r.period,
                "regular_breakfast_price": r.regular_breakfast_price,
                "new_breakfast_price": r.new_breakfast_price,
                "regular_full_pansion_price": r.regular_full_pansion_price,
                "new_full_pansion_price": r.new_full_pansion_price,
                "applied_special_offer": r.applied_special_offer,
                "applied_loyalty": r.applied_loyalty,
                "formula_used": r.formula_used,
                "is_last_room": r.is_last_room,
                "created_at": now,
            }
        )
    with conn.cursor() as cur:
        cur.executemany(insert_sql, data)
    conn.commit()
