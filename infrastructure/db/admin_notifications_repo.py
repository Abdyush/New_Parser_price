from __future__ import annotations

from typing import List


def ensure_admin_notifications_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                acked BOOLEAN NOT NULL DEFAULT FALSE,
                acked_at TIMESTAMP
            )
            """
        )
    conn.commit()


def insert_admin_notification(
    conn,
    telegram_id: int,
    first_name: str,
    last_name: str,
    message: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO admin_notifications (telegram_id, first_name, last_name, message)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (telegram_id, first_name, last_name, message),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row[0])


def list_admin_notifications(conn, limit: int = 10) -> List[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, telegram_id, first_name, last_name, message, created_at, acked
            FROM admin_notifications
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return list(rows)


def mark_admin_notification_acked(conn, notification_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE admin_notifications
            SET acked = TRUE, acked_at = NOW()
            WHERE id = %s
            """,
            (notification_id,),
        )
    conn.commit()
