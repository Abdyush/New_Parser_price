from aiogram import Bot

from infrastructure.db.common_db import get_connection
from app.notifications.service import load_all_guests, load_offers_for_guest
from bot.keyboards.notifications_kb import notifications_keyboard


async def send_notifications(bot: Bot) -> int:
    """
    Рассылает уведомления всем гостям с подходящими предложениями.
    Возвращает количество отправленных сообщений.
    """
    sent = 0

    with get_connection() as conn:
        guests = load_all_guests(conn)

        for guest_id, telegram_id, first_name in guests:
            offers = load_offers_for_guest(conn, guest_id)
            if not offers:
                continue

            text = (
                f"Привет, {first_name}!\n\n"
                "Мы нашли варианты, подходящие под ваш бюджет. "
                "Выберите предложение ниже, чтобы посмотреть детали."
            )

            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=notifications_keyboard(guest_id, offers),
            )
            sent += 1

    return sent
