from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_system_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="▶️ Запустить парсер цен")],
        [KeyboardButton(text="▶️ Запустить парсер офферов")],
        [KeyboardButton(text="🔄 Пересчитать цены")],
        [KeyboardButton(text="⬅️ Назад в админ меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
