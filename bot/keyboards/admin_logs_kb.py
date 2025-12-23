from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_logs_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    can_prev = page > 1
    can_next = page < total_pages

    buttons = [
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"admin_logs_page:{page - 1}" if can_prev else "admin_logs_noop",
            ),
            InlineKeyboardButton(
                text="Обновить",
                callback_data=f"admin_logs_page:{page}",
            ),
            InlineKeyboardButton(
                text="Вперед",
                callback_data=f"admin_logs_page:{page + 1}" if can_next else "admin_logs_noop",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
