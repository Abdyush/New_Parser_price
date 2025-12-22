import os
import html

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_guest_details_repo import PostgresGuestRepository
from bot.keyboards.admin_menu_kb import admin_menu_keyboard
from bot.keyboards.admin_users_kb import users_list_keyboard, back_to_users_keyboard
from bot.keyboards.categories_kb import CATEGORY_MAP


router = Router()

USERS_MENU_TEXT = "👤 Пользователи"
USERS_PER_PAGE = 8


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
    "📨 Уведомления": "Раздел уведомлений в разработке.",
    "📄 Логи": "Раздел логов в разработке.",
    "⚙️ Система": "Раздел системы в разработке.",
}


def _format_price_k(price: int | None) -> str:
    if price is None:
        return "-"
    try:
        price_value = int(price)
    except (TypeError, ValueError):
        return "-"
    if price_value >= 1000:
        return f"{price_value // 1000}к"
    return str(price_value)


def _format_user_label(guest: dict) -> str:
    first_name = (guest.get("first_name") or "").strip()
    last_name = (guest.get("last_name") or "").strip()
    full_name = f"{last_name} {first_name}".strip() or "Без имени"
    return f"{full_name}, {_format_price_k(guest.get('desired_price_per_night'))}"


def _build_guest_profile_text(guest) -> str:
    categories = "\n".join(
        f"• {html.escape(CATEGORY_MAP.get(c, c))}" for c in guest.preferred_categories
    ) or "• не указаны"
    return (
        "<b>Анкета пользователя:</b>\n\n"
        f"<b>Имя:</b> {html.escape(guest.first_name)}\n"
        f"<b>Фамилия:</b> {html.escape(guest.last_name)}\n\n"
        f"<b>Взрослые:</b> {guest.adults}\n"
        f"<b>Дети 4-17:</b> {guest.teens}\n"
        f"<b>Дети 0-3:</b> {guest.infant}\n\n"
        "<b>Категории:</b>\n"
        f"{categories}\n\n"
        f"<b>Статус лояльности:</b> {guest.loyalty_status.value.capitalize()}\n"
        f"<b>Желаемая цена:</b> {guest.desired_price_per_night} ₽"
    )


async def _send_users_page(message: Message, page: int) -> None:
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        total = repo.count_guests()
        total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * USERS_PER_PAGE
        guests = repo.list_guests(limit=USERS_PER_PAGE, offset=offset)
    rows = [(_format_user_label(g), g["telegram_id"]) for g in guests]
    text = f"Пользователи ({page}/{total_pages}):"
    await message.answer(text, reply_markup=users_list_keyboard(rows, page, total_pages))


async def _update_users_page(call: CallbackQuery, page: int) -> None:
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        total = repo.count_guests()
        total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * USERS_PER_PAGE
        guests = repo.list_guests(limit=USERS_PER_PAGE, offset=offset)
    rows = [(_format_user_label(g), g["telegram_id"]) for g in guests]
    text = f"Пользователи ({page}/{total_pages}):"
    await call.message.edit_text(text, reply_markup=users_list_keyboard(rows, page, total_pages))
    await call.answer()


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Админ меню:", reply_markup=admin_menu_keyboard())


@router.message(F.text == USERS_MENU_TEXT)
async def admin_users(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_users_page(message, page=1)


@router.message(F.text.in_(list(ADMIN_MENU_ACTIONS.keys())))
async def admin_menu_action(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer(ADMIN_MENU_ACTIONS[message.text])


@router.callback_query(F.data.startswith("admin_users_page:"))
async def admin_users_page(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    try:
        page = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Некорректная страница.", show_alert=True)
        return
    await _update_users_page(call, page)


@router.callback_query(F.data.startswith("admin_user:"))
async def admin_user_profile(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    try:
        _, tg_id_str, page_str = call.data.split(":")
        tg_id = int(tg_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await call.answer("Некорректный пользователь.", show_alert=True)
        return

    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    if guest is None:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    await call.message.edit_text(
        _build_guest_profile_text(guest),
        reply_markup=back_to_users_keyboard(page),
        parse_mode=ParseMode.HTML,
    )
    await call.answer()
