import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from uuid import UUID
from datetime import date, datetime, timedelta

from psycopg2.extensions import connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.entities import RegularPrice
from infrastructure.db.common_db import get_connection


# -----------------------------
#   МОДЕЛИ ДЛЯ РАБОТЫ В ПАМЯТИ
# -----------------------------

@dataclass
class GuestRow:
    id: int
    first_name: str
    last_name: str
    adults: int
    teens: int
    infant: int
    preferred_categories: List[str]
    loyalty_status: str   # строка из guest_details.loyalty_status


@dataclass
class RoomRow:
    id: int
    category_name: str
    number_of_main_beds: int


@dataclass
class SpecialOffer:
    id: UUID
    categories: List[str]
    formula: Optional[str]
    loyalty_compatible: bool
    booking_start: Optional[date]
    booking_end: Optional[date]


@dataclass
class StayPeriod:
    offer_id: UUID
    stay_start: date
    stay_end: date


@dataclass
class PricedStay:
    """
    Цена на конкретную дату для конкретного гостя и категории
    (ещё не сгруппированная в период).
    """
    guest_id: int
    category: str
    stay_date: date
    regular_breakfast_price: int
    new_breakfast_price: int
    regular_full_pansion_price: int
    new_full_pansion_price: int
    applied_special_offer: Optional[UUID]
    applied_loyalty: Optional[str]
    formula_used: Optional[str]
    is_last_room: bool


@dataclass
class AggregatedRow:
    """
    Уже сгруппированная запись для таблицы guest_prices.
    """
    guest_id: int
    category: str
    period: str
    regular_breakfast_price: int
    new_breakfast_price: int
    regular_full_pansion_price: int
    new_full_pansion_price: int
    applied_special_offer: Optional[UUID]
    applied_loyalty: Optional[str]
    formula_used: Optional[str]
    is_last_room: bool


# -----------------------------
#   ЗАГРУЗКА ДАННЫХ ИЗ БД
# -----------------------------

def load_guests(conn: connection) -> List[GuestRow]:
    cur = conn.cursor()
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


def load_rooms(conn: connection) -> List[RoomRow]:
    cur = conn.cursor()
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


def load_loyalty_discounts(conn: connection) -> Dict[str, int]:
    """
    Возвращает словарь: статус -> процент_скидки (например, 'gold' -> 10)
    """
    cur = conn.cursor()
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


def load_special_offers(conn: connection) -> List[SpecialOffer]:
    """
    Ожидаемые колонки в special_offers:
      id (uuid),
      categories (text[]),
      formula (text),
      loyalty_compatible (bool),
      booking_start (date),
      booking_end (date)
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, categories, formula, loyalty_compatible, booking_start, booking_end
        FROM special_offers
        """
    )
    rows = cur.fetchall()

    offers: List[SpecialOffer] = []
    for r in rows:
        offer_id, categories, formula, compatible, b_start, b_end = r
        offers.append(
            SpecialOffer(
                id=offer_id,
                categories=categories or [],
                formula=formula,
                loyalty_compatible=bool(compatible),
                booking_start=b_start,
                booking_end=b_end,
            )
        )
    return offers


def load_stay_periods(conn: connection) -> Dict[UUID, List[StayPeriod]]:
    """
    Ожидаемые колонки:
      offer_id (uuid),
      stay_start (date),
      stay_end (date)
    Возвращает dict: offer_id -> list[StayPeriod]
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT offer_id, stay_start, stay_end
        FROM special_offer_stay_periods
        """
    )
    rows = cur.fetchall()

    result: Dict[UUID, List[StayPeriod]] = {}
    for offer_id, s_start, s_end in rows:
        sp = StayPeriod(
            offer_id=offer_id,
            stay_start=s_start,
            stay_end=s_end,
        )
        result.setdefault(offer_id, []).append(sp)
    return result


# -----------------------------
#   ПОДБОР КАТЕГОРИЙ И ЦЕН
# -----------------------------

def normalize_category(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def match_categories_for_guest(guest: GuestRow, rooms: List[RoomRow]) -> List[str]:
    preferred = [normalize_category(p) for p in guest.preferred_categories]
    total_people = guest.adults + guest.teens

    matched: List[str] = []

    for room in rooms:
        room_name_lower = normalize_category(room.category_name)

        fits_preference = False

        for pref in preferred:
            if pref == "вилла":
                if "вилла" in room_name_lower:
                    fits_preference = True
            elif "имение сегуна" in pref or "сегуна" in pref:
                if "имение сегуна" in room_name_lower or "сегуна" in room_name_lower:
                    fits_preference = True
            else:
                if pref == room_name_lower:
                    fits_preference = True

        if not fits_preference:
            continue

        if total_people > room.number_of_main_beds:
            continue

        matched.append(room.category_name)

    return matched


def match_regular_prices_for_categories(conn: connection, matched_categories: List[str]) -> List[RegularPrice]:
    """
    Из regular_prices выбирает строки, где:
    room_category ILIKE %название%
    """
    if not matched_categories:
        return []

    cursor = conn.cursor()

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


# -----------------------------
#   ПРОВЕРКА ПРИМЕНИМОСТИ ОФФЕРОВ
# -----------------------------

def offer_matches_category(offer: SpecialOffer, room_category: str) -> bool:
    """
    Специальные значения:
      "Все виллы"     -> любые категории, содержащие "вилла"
      "Все категории" -> любые категории
    Остальные -> точное совпадение по нормализованной строке.
    """
    cats = offer.categories or []
    if not cats:
        return False

    room_norm = normalize_category(room_category)
    norm_cats = [normalize_category(c) for c in cats]

    if any(c == "все категории" for c in norm_cats):
        return True

    if any(c == "все виллы" for c in norm_cats):
        return "вилла" in room_norm

    return room_norm in norm_cats


def offer_matches_stay_date(offer: SpecialOffer,
                            periods_map: Dict[UUID, List[StayPeriod]],
                            stay_dt: date) -> bool:
    periods = periods_map.get(offer.id, [])
    for p in periods:
        if p.stay_start <= stay_dt <= p.stay_end:
            return True
    return False


def offer_matches_booking_date(offer: SpecialOffer, today: date) -> bool:
    return (offer.booking_start is None or offer.booking_start <= today) and \
           (offer.booking_end is None or today <= offer.booking_end)


def apply_formula(formula: Optional[str], base_price: int) -> (int, Optional[str]):
    """
    Формат: "N = (C * 3) / 4"
    C — старая цена, N — новая.
    """
    if not formula:
        return base_price, None

    text = formula.strip()
    if "=" in text:
        _, rhs = text.split("=", 1)
    else:
        rhs = text

    expr = rhs.replace("C", str(base_price)).replace("N", "").strip()

    try:
        new_value = eval(expr, {"__builtins__": {}}, {})
    except Exception:
        return base_price, formula

    try:
        new_int = int(round(float(new_value)))
    except Exception:
        new_int = base_price

    return new_int, formula


def calc_price_with_discounts(
    base_price: int,
    guest_loyalty: Optional[str],
    loyalty_discounts: Dict[str, int],
    offer: Optional[SpecialOffer]
) -> (int, Optional[UUID], Optional[str], Optional[str]):
    """
    Возвращает:
      new_price,
      applied_offer_id,
      applied_loyalty_status,
      formula_used (формула оффера, если была)
    """
    applied_offer_id: Optional[UUID] = None
    applied_loyalty: Optional[str] = None
    formula_used: Optional[str] = None

    price_after_offer = base_price

    # 1) Спецпредложение
    if offer and offer.formula:
        price_after_offer, formula_used = apply_formula(offer.formula, base_price)
        applied_offer_id = offer.id

    # 2) Лояльность
    final_price = price_after_offer
    if guest_loyalty:
        status_norm = guest_loyalty.strip().lower()
        discount_percent = loyalty_discounts.get(status_norm)
        if discount_percent:
            # Если оффер не совместим — не применяем
            if (not offer) or offer.loyalty_compatible:
                final_price = int(round(price_after_offer * (100 - discount_percent) / 100))
                applied_loyalty = guest_loyalty

    return final_price, applied_offer_id, applied_loyalty, formula_used


def build_priced_stays_for_guest(
    guest: GuestRow,
    matched_prices: List[RegularPrice],
    loyalty_discounts: Dict[str, int],
    offers: List[SpecialOffer],
    periods_map: Dict[UUID, List[StayPeriod]],
    today: date,
) -> List[PricedStay]:

    stays: List[PricedStay] = []

    for rp in matched_prices:
        # ищем применимый оффер
        applicable_offer: Optional[SpecialOffer] = None
        for off in offers:
            if not offer_matches_category(off, rp.category):
                continue
            if not offer_matches_stay_date(off, periods_map, rp.date):
                continue
            if not offer_matches_booking_date(off, today):
                continue
            applicable_offer = off
            break  # берём первое совпадение (при желании можно выбирать «лучшее»)

        # только завтраки
        new_breakfast, offer_id_bf, loyalty_bf, formula_used = calc_price_with_discounts(
            base_price=rp.only_breakfast,
            guest_loyalty=guest.loyalty_status,
            loyalty_discounts=loyalty_discounts,
            offer=applicable_offer,
        )

        # полный пансион
        new_full, offer_id_fp, loyalty_fp, _ = calc_price_with_discounts(
            base_price=rp.full_pansion,
            guest_loyalty=guest.loyalty_status,
            loyalty_discounts=loyalty_discounts,
            offer=applicable_offer,
        )

        applied_offer_id = offer_id_bf or offer_id_fp
        applied_loyalty = loyalty_bf or loyalty_fp

        stays.append(
            PricedStay(
                guest_id=guest.id,
                category=str(rp.category),
                stay_date=rp.date,
                regular_breakfast_price=rp.only_breakfast,
                new_breakfast_price=new_breakfast,
                regular_full_pansion_price=rp.full_pansion,
                new_full_pansion_price=new_full,
                applied_special_offer=applied_offer_id,
                applied_loyalty=applied_loyalty,
                formula_used=formula_used,
                is_last_room=rp.is_last_room,
            )
        )

    return stays


# -----------------------------
#   ГРУППИРОВКА В ПЕРИОДЫ
# -----------------------------

def group_stays_into_periods(stays: List[PricedStay]) -> List[AggregatedRow]:
    """
    Группируем подряд идущие даты с одинаковыми:
      - guest_id
      - категорией
      - ценами
      - применёнными скидками
      - is_last_room
    period: 'YYYY-MM-DD' или 'YYYY-MM-DD..YYYY-MM-DD'
    """
    if not stays:
        return []

    stays_sorted = sorted(stays, key=lambda s: (s.guest_id, s.category, s.stay_date))

    result: List[AggregatedRow] = []

    current = stays_sorted[0]
    start_date = current.stay_date
    prev_date = current.stay_date

    def make_period_str(start: date, end: date) -> str:
        if start == end:
            return start.isoformat()
        return f"{start.isoformat()}..{end.isoformat()}"

    def push_agg(stay: PricedStay, start: date, end: date):
        result.append(
            AggregatedRow(
                guest_id=stay.guest_id,
                category=stay.category,
                period=make_period_str(start, end),
                regular_breakfast_price=stay.regular_breakfast_price,
                new_breakfast_price=stay.new_breakfast_price,
                regular_full_pansion_price=stay.regular_full_pansion_price,
                new_full_pansion_price=stay.new_full_pansion_price,
                applied_special_offer=stay.applied_special_offer,
                applied_loyalty=stay.applied_loyalty,
                formula_used=stay.formula_used,
                is_last_room=stay.is_last_room,
            )
        )

    for s in stays_sorted[1:]:
        same_key = (
            s.guest_id == current.guest_id
            and s.category == current.category
            and s.regular_breakfast_price == current.regular_breakfast_price
            and s.new_breakfast_price == current.new_breakfast_price
            and s.regular_full_pansion_price == current.regular_full_pansion_price
            and s.new_full_pansion_price == current.new_full_pansion_price
            and s.applied_special_offer == current.applied_special_offer
            and s.applied_loyalty == current.applied_loyalty
            and s.formula_used == current.formula_used
            and s.is_last_room == current.is_last_room
        )

        is_next_day = (s.stay_date == prev_date + timedelta(days=1))

        if same_key and is_next_day:
            prev_date = s.stay_date
            current = s
        else:
            push_agg(current, start_date, prev_date)
            current = s
            start_date = s.stay_date
            prev_date = s.stay_date

    push_agg(current, start_date, prev_date)

    return result


# -----------------------------
#   СОХРАНЕНИЕ В guest_prices
# -----------------------------

def save_guest_prices(conn: connection, rows: List[AggregatedRow]) -> None:
    if not rows:
        return

    cur = conn.cursor()
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
    cur.executemany(insert_sql, data)
    conn.commit()


# -----------------------------
#   MAIN
# -----------------------------

def main():
    today = date.today()

    with get_connection() as conn:
        guests = load_guests(conn)
        rooms = load_rooms(conn)
        loyalty_discounts = load_loyalty_discounts(conn)
        offers = load_special_offers(conn)
        stay_periods = load_stay_periods(conn)

        for guest in guests:
            print(f"Обрабатываем гостя: {guest.first_name} {guest.last_name} (id={guest.id})")

            # очищаем старые расчёты для гостя
            cur = conn.cursor()
            cur.execute("DELETE FROM guest_prices WHERE guest_id = %s", (guest.id,))
            conn.commit()

            matched_categories = match_categories_for_guest(guest, rooms)
            if not matched_categories:
                print("  Нет подходящих категорий.")
                continue

            regular_prices = match_regular_prices_for_categories(conn, matched_categories)
            if not regular_prices:
                print("  Не найдено цен в regular_prices.")
                continue

            stays = build_priced_stays_for_guest(
                guest=guest,
                matched_prices=regular_prices,
                loyalty_discounts=loyalty_discounts,
                offers=offers,
                periods_map=stay_periods,
                today=today,
            )

            aggregated = group_stays_into_periods(stays)
            save_guest_prices(conn, aggregated)

            print(f"  Сохранено {len(aggregated)} строк в guest_prices")
            print("-" * 40)


if __name__ == "__main__":
    main()