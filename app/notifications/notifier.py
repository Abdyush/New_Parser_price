from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from infrastructure.db.common_db import get_connection
from app.notifications.service import load_all_guests, load_offers_for_guest, filter_offers_by_preferences
from bot.keyboards.notifications_kb import notifications_keyboard
from app.matching.pricing_service import run_pricing


async def send_notifications(bot: Bot) -> int:
    """
    Рассылает уведомления всем гостям с подходящими предложениями.
    Возвращает количество отправленных сообщений.
    """
    sent = 0

    # Пересчитываем guest_prices перед рассылкой, чтобы учесть свежий статус лояльности/оферы
    run_pricing()

    with get_connection() as conn:
        guests = load_all_guests(conn)

        for guest_id, telegram_id, first_name in guests:
            offers = filter_offers_by_preferences(
                conn,
                guest_id,
                load_offers_for_guest(conn, guest_id),
            )
            if not offers:
                await bot.send_message(
                    chat_id=telegram_id,
                    text="На данный момент, в отеле нет номеров удовлетворяющих Вашим требованиям",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Изменить параметры", callback_data="edit")],
                            [InlineKeyboardButton(text="Ожидаем дальше", callback_data="wait_ok")],
                        ]
                    ),
                )
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
