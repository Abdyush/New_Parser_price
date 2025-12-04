from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

status_loyalty = ['None', 'White', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']

def loyalty_keyboard(selected: str | None = None):
    rows = []

    for status in status_loyalty:
        text = f"✔ {status}" if selected == status else status
        data = f"loy_{status}"
        rows.append([InlineKeyboardButton(text=text, callback_data=data)])

    rows.append([
        InlineKeyboardButton(text="Подтвердить", callback_data="loyalty_done"),
        InlineKeyboardButton(text="Отмена", callback_data="loyalty_cancel"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)