from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List

from app.notifications.service import GuestPriceNotification


def notifications_keyboard(guest_id: int, offers: List[GuestPriceNotification]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком категорий:
    на кнопке: только сокращённое имя категории
    callback_data: "n_it_<guest_price_id>"
    Внизу - кнопка "Ознакомился, спасибо!"
    """
    buttons = []

    # Сортируем предложения по цене (мин. доступной), пустые цены в конец
    def _price(o: GuestPriceNotification):
        return (
            o.new_breakfast_price
            if o.new_breakfast_price is not None
            else o.new_full_pansion_price
            if o.new_full_pansion_price is not None
            else float("inf")
        )

    for offer in sorted(offers, key=_price):
        # Берём главную цену (приоритет — с завтраком)
        price = offer.new_breakfast_price or offer.new_full_pansion_price

        # Сокращаем название категории до текста перед первой скобкой
        category_short = offer.category.split("(", 1)[0].strip() if offer.category else "Категория"

        # Кнопка только с названием категории (остальные детали показываем после клика)
        text = category_short

        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"n_it_{offer.id}")]
        )

    # Кнопка подтверждения
    buttons.append(
        [InlineKeyboardButton(text="Ознакомился, спасибо!", callback_data="n_ack")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def notification_details_keyboard(offer: GuestPriceNotification) -> InlineKeyboardMarkup:
    """
    Кнопки под деталями:
    1) Назад к категориям
    2) Заинтересовало! Написать Никите (url)
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад к категориям",
                    callback_data=f"n_back_{offer.guest_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Заинтересовало! Написать Никите",
                    url="https://t.me/Abdyushev_Nikita"
                )
            ],
        ]
    )
