from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List

from app.notifications.service import CategoryNotification


def notifications_keyboard(guest_id: int, offers: List[CategoryNotification]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком категорий:
    на кнопке: только сокращённое имя категории
    callback_data: "n_it_<guest_price_id>"
    Внизу - кнопка "Ознакомился, спасибо!"
    """
    buttons = []

    # Сортируем предложения по цене (мин. доступной), пустые цены в конец
    def _price(cat: CategoryNotification):
        best = float("inf")
        for item in cat.items:
            for val in (item.new_breakfast_price, item.new_full_pansion_price):
                if val is not None:
                    best = min(best, val)
        return best

    for idx, offer in enumerate(sorted(offers, key=_price)):
        category_short = offer.category.split("(", 1)[0].strip() if offer.category else "Категория"
        text = category_short

        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"n_it_{offer.items[0].guest_id}_{idx}")]
        )

    # Кнопка подтверждения
    buttons.append(
        [InlineKeyboardButton(text="Ознакомился, спасибо!", callback_data="n_ack")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def notification_details_keyboard(guest_id: int) -> InlineKeyboardMarkup:
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
                    callback_data=f"n_back_{guest_id}"
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
