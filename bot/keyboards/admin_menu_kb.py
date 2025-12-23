from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="👤 Пользователи")],
        [KeyboardButton(text="📨 Уведомления")],
        [KeyboardButton(text="📄 Логи")],
        [KeyboardButton(text="⚙️ Система")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
