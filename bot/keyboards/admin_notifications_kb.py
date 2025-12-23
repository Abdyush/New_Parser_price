from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def new_user_notification_keyboard(telegram_id: int, notification_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Посмотреть анкету",
                    callback_data=f"admin_notif_view:{telegram_id}:{notification_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Принято, спасибо!",
                    callback_data=f"admin_notif_ack:{notification_id}",
                )
            ],
        ]
    )


def admin_notifications_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад в меню")]],
        resize_keyboard=True,
    )
