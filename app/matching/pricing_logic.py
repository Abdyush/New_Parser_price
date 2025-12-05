from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from core.entities import RegularPrice

from .models import (
    AggregatedRow,
    GuestRow,
    PricedStay,
    RoomRow,
    SpecialOfferData,
    StayPeriodData,
)


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


def offer_matches_category(offer: SpecialOfferData, room_category: str) -> bool:
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


def offer_matches_stay_date(
    offer: SpecialOfferData,
    periods_map: Dict[UUID, List[StayPeriodData]],
    stay_dt: date,
) -> bool:
    periods = periods_map.get(offer.id, [])
    for p in periods:
        if p.stay_start <= stay_dt <= p.stay_end:
            return True
    return False


def offer_matches_booking_date(offer: SpecialOfferData, today: date) -> bool:
    return (offer.booking_start is None or offer.booking_start <= today) and \
           (offer.booking_end is None or today <= offer.booking_end)


def apply_formula(formula: Optional[str], base_price: int) -> Tuple[int, Optional[str]]:
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
    offer: Optional[SpecialOfferData],
) -> Tuple[int, Optional[UUID], Optional[str], Optional[str]]:
    applied_offer_id: Optional[UUID] = None
    applied_loyalty: Optional[str] = None
    formula_used: Optional[str] = None

    price_after_offer = base_price

    if offer and offer.formula:
        price_after_offer, formula_used = apply_formula(offer.formula, base_price)
        applied_offer_id = offer.id

    final_price = price_after_offer
    if guest_loyalty:
        status_norm = guest_loyalty.strip().lower()
        discount_percent = loyalty_discounts.get(status_norm)
        if discount_percent:
            if (not offer) or offer.loyalty_compatible:
                final_price = int(round(price_after_offer * (100 - discount_percent) / 100))
                applied_loyalty = guest_loyalty

    return final_price, applied_offer_id, applied_loyalty, formula_used


def build_priced_stays_for_guest(
    guest: GuestRow,
    matched_prices: List[RegularPrice],
    loyalty_discounts: Dict[str, int],
    offers: List[SpecialOfferData],
    periods_map: Dict[UUID, List[StayPeriodData]],
    today: date,
) -> List[PricedStay]:
    stays: List[PricedStay] = []

    for rp in matched_prices:
        applicable_offer: Optional[SpecialOfferData] = None
        for off in offers:
            if not offer_matches_category(off, rp.category):
                continue
            if not offer_matches_stay_date(off, periods_map, rp.date):
                continue
            if not offer_matches_booking_date(off, today):
                continue
            applicable_offer = off
            break

        new_breakfast, offer_id_bf, loyalty_bf, formula_used = calc_price_with_discounts(
            base_price=rp.only_breakfast,
            guest_loyalty=guest.loyalty_status,
            loyalty_discounts=loyalty_discounts,
            offer=applicable_offer,
        )

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


def group_stays_into_periods(stays: List[PricedStay]) -> List[AggregatedRow]:
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
