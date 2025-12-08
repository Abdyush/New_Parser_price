from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    kb = [
        [InlineKeyboardButton(text="Все отлично! Жду уведомлений 🔔", callback_data="wait_ok")],
        [InlineKeyboardButton(text="Редактировать данные ✏️", callback_data="edit")],
        [InlineKeyboardButton(text="Мои категории 🏨", callback_data="edit_categories")],
        [InlineKeyboardButton(text="Изменить цену 💰", callback_data="edit_price")],
        [InlineKeyboardButton(text="Изменить статус ⭐", callback_data="edit_status")],
        [InlineKeyboardButton(text="Доступные номера", callback_data="show_available")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
