from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def users_list_keyboard(rows: list[tuple[str, int]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    for label, telegram_id in rows:
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"admin_user:{telegram_id}:{page}")]
        )

    prev_page = page - 1 if page > 1 else page
    next_page = page + 1 if page < total_pages else page
    buttons.append(
        [
            InlineKeyboardButton(text="<-", callback_data=f"admin_users_page:{prev_page}"),
            InlineKeyboardButton(text="->", callback_data=f"admin_users_page:{next_page}"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_users_keyboard(page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад к списку", callback_data=f"admin_users_page:{page}")]
        ]
    )
