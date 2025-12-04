from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

CATEGORY_MAP = {
    "deluxe": "Делюкс",
    "family_suite": "Семейный люкс",
    "spa_apart": "Апартаменты СПА",
    "elegant": "Люкс Элегант",
    "connect_deluxe": "Коннект делюкс",
    "shogun": "Апартаменты «имение Сёгуна»",
    "royal": "Королевский люкс",
    "penthouse": "Пентхаус",
    "villa": "Вилла",
}
# Обратное отображение: человекочитаемое название -> ключ категории
CATEGORY_REVERSE = {v: k for k, v in CATEGORY_MAP.items()}

def categories_keyboard(selected=None):
    if selected is None:
        selected = []

    kb = []

    for key, title in CATEGORY_MAP.items():
        prefix = "✓ " if key in selected else ""
        kb.append([
            InlineKeyboardButton(
                text=prefix + title,
                callback_data=f"cat:{key}"
            )
        ])

    kb.append([
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="cat_done")
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)
