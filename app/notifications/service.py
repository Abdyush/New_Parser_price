from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from psycopg2.extensions import connection
from psycopg2.errors import UndefinedTable

from app.matching.pricing_logic import normalize_category


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
    applied_special_offer_text: Optional[str]
    applied_special_offer_min_days: Optional[int]
    applied_loyalty: Optional[str]
    loyalty_discount_percent: Optional[int]
    formula_used: Optional[str]
    is_last_room: Optional[str]


@dataclass
class CategoryNotification:
    category: str
    items: List[GuestPriceNotification]


@dataclass
class ParserStatus:
    status: str
    last_completed_date: Optional[date]
    failed_at: Optional[date]
    message: Optional[str]


def filter_offers_by_preferences(conn: connection, guest_id: int, offers: List[CategoryNotification]) -> List[CategoryNotification]:
    """
    Оставляем только категории, которые соответствуют предпочтениям гостя.
    Сопоставление по подстроке в нижнем регистре: если предпочтений нет, возвращаем всё.
    """
    cur = conn.cursor()
    cur.execute("SELECT preferred_categories FROM guest_details WHERE id = %s", (guest_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return offers

    prefs = [normalize_category(str(p)) for p in row[0] if p]
    if not prefs:
        return offers

    filtered: List[CategoryNotification] = []
    for cat in offers:
        cat_norm = normalize_category(cat.category or "")
        if any(pref in cat_norm or cat_norm in pref for pref in prefs):
            filtered.append(cat)

    return filtered


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


def load_offers_for_guest(conn: connection, guest_id: int) -> List[CategoryNotification]:
    """
    Берём категории, где есть хотя бы один период с ценой <= desired_price гостя,
    но для каждой такой категории возвращаем все её периоды.
    """

    cur = conn.cursor()
    cur.execute(
        """
        WITH desired_categories AS (
            SELECT DISTINCT gp.category
            FROM guest_prices gp
            JOIN guest_details gd ON gd.id = gp.guest_id
            WHERE gp.guest_id = %s
              AND (
                    (gp.new_breakfast_price IS NOT NULL
                     AND gp.new_breakfast_price <= gd.desired_price_per_night)
                 OR (gp.new_full_pansion_price IS NOT NULL
                     AND gp.new_full_pansion_price <= gd.desired_price_per_night)
              )
        )
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
            so.text AS special_text,
            so.min_days,
            gp.applied_loyalty,
            ld.discount_percent,
            gp.formula_used,
            gp.is_last_room
        FROM guest_prices gp
        JOIN desired_categories dc ON dc.category = gp.category
        LEFT JOIN special_offers so
            ON so.id = gp.applied_special_offer
        LEFT JOIN loyalty_discounts ld
            ON ld.level = gp.applied_loyalty
        WHERE gp.guest_id = %s
        ORDER BY gp.category, gp.period;
        """,
        (guest_id, guest_id),
    )

    rows = cur.fetchall()
    by_cat: dict[str, List[GuestPriceNotification]] = {}

    for r in rows:
        item = GuestPriceNotification(
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
            applied_special_offer_text=r[10],
            applied_special_offer_min_days=r[11],
            applied_loyalty=r[12],
            loyalty_discount_percent=r[13],
            formula_used=r[14],
            is_last_room=r[15],
        )
        by_cat.setdefault(item.category, []).append(item)

    results: List[CategoryNotification] = []
    for cat, items in by_cat.items():
        results.append(CategoryNotification(category=cat, items=items))

    return results


def load_single_offer(conn: connection, guest_id: int, category: str) -> Optional[CategoryNotification]:
    """
    Возвращает все периоды конкретной категории гостя.
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
            so.text AS special_text,
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
        WHERE gp.guest_id = %s AND gp.category = %s
        ORDER BY gp.period;
        """,
        (guest_id, category),
    )
    rows = cur.fetchall()
    if not rows:
        return None

    items: List[GuestPriceNotification] = []
    for r in rows:
        items.append(
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
                applied_special_offer_text=r[10],
                applied_special_offer_min_days=r[11],
                applied_loyalty=r[12],
                loyalty_discount_percent=r[13],
                formula_used=r[14],
                is_last_room=r[15],
            )
        )

    return CategoryNotification(category=category, items=items)


def load_parser_status(conn: connection) -> Optional[ParserStatus]:
    """Возвращает статус последнего прогона парсера цен, если таблица доступна."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT status, last_completed_date, failed_at, message
            FROM price_parser_status
            WHERE id = 1
            """
        )
    except UndefinedTable:
        conn.rollback()
        return None
    except Exception:
        conn.rollback()
        return None

    row = cur.fetchone()
    if not row:
        return None

    return ParserStatus(
        status=row[0],
        last_completed_date=row[1],
        failed_at=row[2],
        message=row[3],
    )
