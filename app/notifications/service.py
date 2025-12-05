from dataclasses import dataclass
from typing import List, Optional

from psycopg2.extensions import connection


@dataclass
class GuestPriceNotification:
    id: int
    guest_id: int
    category: str
    period: str
    regular_breakfast_price: Optional[int]
    new_breakfast_price: Optional[int]
    regular_full_pansion_price: Optional[int]
    new_full_pansion_price: Optional[int]
    applied_special_offer_id: Optional[str]
    applied_special_offer_title: Optional[str]
    applied_special_offer_min_days: Optional[int]
    applied_loyalty: Optional[str]
    loyalty_discount_percent: Optional[int]
    formula_used: Optional[str]
    is_last_room: bool


def load_all_guests(conn: connection) -> list[tuple[int, int, str]]:
    """
    Возвращает список гостей: (guest_id, telegram_id, first_name)
    Можно добавить фильтр по 'подписан на уведомления', если введёшь такой флаг.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, telegram_id, first_name
        FROM guest_details
        WHERE telegram_id IS NOT NULL
        """
    )
    return cur.fetchall()


def load_offers_for_guest(conn: connection, guest_id: int) -> List[GuestPriceNotification]:
    """
    Берём все записи из guest_prices для гостя,
    где новая цена <= desired_price_per_night гостя.
    Джойним спецпредложения и скидку лояльности.
    """

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            gp.id,
            gp.guest_id,
            gp.category,
            gp.period,
            gp.regular_breakfast_price,
            gp.new_breakfast_price,
            gp.regular_full_pansion_price,
            gp.new_full_pansion_price,
            gp.applied_special_offer,
            so.title AS special_title,
            so.min_days,
            gp.applied_loyalty,
            ld.discount_percent,
            gp.formula_used,
            gp.is_last_room
        FROM guest_prices gp
        JOIN guest_details gd
            ON gd.id = gp.guest_id
        LEFT JOIN special_offers so
            ON so.id = gp.applied_special_offer
        LEFT JOIN loyalty_discounts ld
            ON ld.level = gp.applied_loyalty    
        WHERE gp.guest_id = %s
          AND (
                (gp.new_breakfast_price IS NOT NULL
                 AND gp.new_breakfast_price <= gd.desired_price_per_night)
             OR (gp.new_full_pansion_price IS NOT NULL
                 AND gp.new_full_pansion_price <= gd.desired_price_per_night)
          )
        ORDER BY gp.category, gp.period;
        """,
        (guest_id,),
    )

    rows = cur.fetchall()
    results: List[GuestPriceNotification] = []

    for r in rows:
        results.append(
            GuestPriceNotification(
                id=r[0],
                guest_id=r[1],
                category=r[2],
                period=r[3],
                regular_breakfast_price=r[4],
                new_breakfast_price=r[5],
                regular_full_pansion_price=r[6],
                new_full_pansion_price=r[7],
                applied_special_offer_id=r[8],
                applied_special_offer_title=r[9],
                applied_special_offer_min_days=r[10],
                applied_loyalty=r[11],
                loyalty_discount_percent=r[12],
                formula_used=r[13],
                is_last_room=r[14],
            )
        )
    return results


def load_single_offer(conn: connection, guest_price_id: int) -> Optional[GuestPriceNotification]:
    """
    Нужен, когда пользователь нажимает на кнопку конкретной категории.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            gp.id,
            gp.guest_id,
            gp.category,
            gp.period,
            gp.regular_breakfast_price,
            gp.new_breakfast_price,
            gp.regular_full_pansion_price,
            gp.new_full_pansion_price,
            gp.applied_special_offer,
            so.title AS special_title,
            so.min_days,
            gp.applied_loyalty,
            ld.discount_percent,
            gp.formula_used,
            gp.is_last_room
        FROM guest_prices gp
        LEFT JOIN special_offers so
            ON so.id = gp.applied_special_offer
        LEFT JOIN loyalty_discounts ld
            ON ld.level = gp.applied_loyalty
        WHERE gp.id = %s;
        """,
        (guest_price_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    return GuestPriceNotification(
        id=row[0],
        guest_id=row[1],
        category=row[2],
        period=row[3],
        regular_breakfast_price=row[4],
        new_breakfast_price=row[5],
        regular_full_pansion_price=row[6],
        new_full_pansion_price=row[7],
        applied_special_offer_id=row[8],
        applied_special_offer_title=row[9],
        applied_special_offer_min_days=row[10],
        applied_loyalty=row[11],
        loyalty_discount_percent=row[12],
        formula_used=row[13],
        is_last_room=row[14],
    )
