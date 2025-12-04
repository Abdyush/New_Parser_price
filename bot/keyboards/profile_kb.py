from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def profile_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Редактировать данные")],
        ],
        resize_keyboard=True
    )