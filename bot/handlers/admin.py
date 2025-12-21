import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.admin_menu_kb import admin_menu_keyboard


router = Router()


def _get_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_TELEGRAM_ID", "")
    ids: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            continue
    return ids


def _is_admin(user_id: int) -> bool:
    return user_id in _get_admin_ids()


ADMIN_MENU_ACTIONS = {
    "📊 Статистика": "Раздел статистики в разработке.",
    "👤 Пользователи": "Раздел пользователей в разработке.",
    "📨 Уведомления": "Раздел уведомлений в разработке.",
    "📄 Логи": "Раздел логов в разработке.",
    "⚙️ Система": "Раздел системы в разработке.",
}


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Админ меню:", reply_markup=admin_menu_keyboard())


@router.message(F.text.in_(list(ADMIN_MENU_ACTIONS.keys())))
async def admin_menu_action(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer(ADMIN_MENU_ACTIONS[message.text])
