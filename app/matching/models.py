from dataclasses import dataclass
from datetime import date
from typing import List, Optional
from uuid import UUID


@dataclass
class GuestRow:
    id: int
    first_name: str
    last_name: str
    adults: int
    teens: int
    infant: int
    preferred_categories: List[str]
    loyalty_status: str


@dataclass
class RoomRow:
    id: int
    category_name: str
    number_of_main_beds: int


@dataclass
class SpecialOfferData:
    id: UUID
    categories: List[str]
    formula: Optional[str]
    min_days: Optional[int]
    loyalty_compatible: bool
    booking_start: Optional[date]
    booking_end: Optional[date]


@dataclass
class StayPeriodData:
    offer_id: UUID
    stay_start: date
    stay_end: date


@dataclass
class PricedStay:
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
    is_last_room: str
