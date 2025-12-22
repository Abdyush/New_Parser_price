from datetime import datetime
from typing import Optional, List

import psycopg2
from psycopg2.extras import RealDictCursor

from core.entities import GuestDetails, LoyaltyStatus


class PostgresGuestRepository:
    """
    Репозиторий для сохранения и получения данных гостей.
    Работает с таблицей guest_details.
    """

    def __init__(self, conn):
        self.conn = conn

    # -------------------------------
    # Сохранение нового гостя
    # -------------------------------
    def save_guest(self, guest: GuestDetails):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO guest_details (
                    telegram_id, first_name, last_name,
                    adults, teens, infant,
                    preferred_categories, loyalty_status,
                    desired_price_per_night, created_at
                ) VALUES (
                    %(telegram_id)s, %(first_name)s, %(last_name)s,
                    %(adults)s, %(teens)s, %(infant)s,
                    %(preferred_categories)s, %(loyalty_status)s,
                    %(desired_price_per_night)s, %(created_at)s
                )
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    adults = EXCLUDED.adults,
                    teens = EXCLUDED.teens,
                    infant = EXCLUDED.infant,
                    preferred_categories = EXCLUDED.preferred_categories,
                    loyalty_status = EXCLUDED.loyalty_status,
                    desired_price_per_night = EXCLUDED.desired_price_per_night;
                """,
                {
                    "telegram_id": guest.telegram_id,
                    "first_name": guest.first_name,
                    "last_name": guest.last_name,
                    "adults": guest.adults,
                    "teens": guest.teens,
                    "infant": guest.infant,
                    "preferred_categories": guest.preferred_categories,
                    "loyalty_status": guest.loyalty_status.value,
                    "desired_price_per_night": guest.desired_price_per_night,
                    "created_at": guest.created_at,
                }
            )
        self.conn.commit()

    # -------------------------------
    # Получение гостя по Telegram ID
    # -------------------------------
    def get_by_telegram_id(self, telegram_id: int) -> GuestDetails | None:
        cur = self.conn.cursor()

        cur.execute("""
            SELECT id, telegram_id, first_name, last_name,
                   adults, teens, infant,
                   preferred_categories, loyalty_status,
                   desired_price_per_night, created_at
            FROM guest_details
            WHERE telegram_id = %s
        """, (telegram_id,))

        row = cur.fetchone()
        cur.close()

        if row is None:
            return None

        return GuestDetails(
            id=row[0],
            telegram_id=row[1],
            first_name=row[2],
            last_name=row[3],
            adults=row[4],
            teens=row[5],
            infant=row[6],
            preferred_categories=row[7],
            loyalty_status=LoyaltyStatus(row[8]),
            desired_price_per_night=row[9],
            created_at=row[10]
        )

    # -------------------------------
    # Обновление данных гостя
    # -------------------------------
    def update_guest(self, guest: GuestDetails):
        """
        Обновляет запись гостя по его ID.
        """

        if guest.id is None:
            raise ValueError("guest.id должен быть установлен перед обновлением")

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE guest_details
                SET
                    telegram_id = %s,
                    first_name = %s,
                    last_name = %s,
                    adults = %s,
                    teens = %s,
                    infant = %s,
                    preferred_categories = %s,
                    loyalty_status = %s,
                    desired_price_per_night = %s
                WHERE id = %s
                """,
                (
                    guest.telegram_id,
                    guest.first_name,
                    guest.last_name,
                    guest.adults,
                    guest.teens,
                    guest.infant,
                    guest.preferred_categories,
                    guest.loyalty_status.value,
                    guest.desired_price_per_night,
                    guest.id,
                )
            )

            self.conn.commit()
            
    def set_active(self, telegram_id: int, flag: bool):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE guest_details SET is_active=%s WHERE telegram_id=%s",
                (flag, telegram_id)
            )
        self.conn.commit()

    def count_guests(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM guest_details")
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def list_guests(self, limit: int, offset: int) -> List[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT telegram_id, first_name, last_name, desired_price_per_night
                FROM guest_details
                ORDER BY created_at DESC NULLS LAST, id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()

        guests: List[dict] = []
        for telegram_id, first_name, last_name, desired_price_per_night in rows:
            guests.append(
                {
                    "telegram_id": telegram_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "desired_price_per_night": desired_price_per_night,
                }
            )
        return guests
