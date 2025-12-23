import os
import html
import asyncio

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_guest_details_repo import PostgresGuestRepository
from infrastructure.db.system_event_log_repo import (
    ensure_system_event_log_table,
    list_events,
    count_events,
)
from infrastructure.db.admin_notifications_repo import (
    ensure_admin_notifications_table,
    list_admin_notifications,
    mark_admin_notification_acked,
)
from bot.keyboards.admin_menu_kb import admin_menu_keyboard
from bot.keyboards.admin_users_kb import users_list_keyboard, back_to_users_keyboard
from bot.keyboards.admin_logs_kb import admin_logs_keyboard
from bot.keyboards.admin_system_kb import admin_system_keyboard
from bot.keyboards.admin_notifications_kb import admin_notifications_menu_keyboard
from bot.keyboards.categories_kb import CATEGORY_MAP
from scripts import run_price_parser, run_offers_parser, run_price_matching


router = Router()

USERS_MENU_TEXT = "\U0001F464 \u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438"
NOTIFICATIONS_MENU_TEXT = "\U0001F4E8 \u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F"
LOGS_MENU_TEXT = "\U0001F4C4 \u041B\u043E\u0433\u0438"
SYSTEM_MENU_TEXT = "\u2699\ufe0f \u0421\u0438\u0441\u0442\u0435\u043C\u0430"
USERS_PER_PAGE = 8
LOGS_PER_PAGE = 10
SYSTEM_ACTION_PRICE_PARSER = "\u25B6\ufe0f \u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u0430\u0440\u0441\u0435\u0440 \u0446\u0435\u043D"
SYSTEM_ACTION_OFFERS_PARSER = "\u25B6\ufe0f \u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u0430\u0440\u0441\u0435\u0440 \u043E\u0444\u0444\u0435\u0440\u043E\u0432"
SYSTEM_ACTION_REPRICE = "\U0001F504 \u041F\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044C \u0446\u0435\u043D\u044B"
SYSTEM_ACTION_BACK = "\u2B05\ufe0f \u041D\u0430\u0437\u0430\u0434 \u0432 \u0430\u0434\u043C\u0438\u043D \u043C\u0435\u043D\u044E"
NOTIFICATIONS_BACK_TEXT = "\u2B05\ufe0f \u041D\u0430\u0437\u0430\u0434 \u0432 \u043C\u0435\u043D\u044E"


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
    "\U0001F4CA \u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430": "\u0420\u0430\u0437\u0434\u0435\u043B \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0438 \u0432 \u0440\u0430\u0437\u0440\u0430\u0431\u043E\u0442\u043A\u0435.",
}


def _format_price_k(price: int | None) -> str:
    if price is None:
        return "-"
    try:
        price_value = int(price)
    except (TypeError, ValueError):
        return "-"
    if price_value >= 1000:
        return f"{price_value // 1000}\u043a"
    return str(price_value)


def _format_user_label(guest: dict) -> str:
    first_name = (guest.get("first_name") or "").strip()
    last_name = (guest.get("last_name") or "").strip()
    full_name = f"{last_name} {first_name}".strip() or "\u0418\u043c\u044f \u043d\u0435 \u0437\u0430\u0434\u0430\u043d\u043e"
    return f"{full_name}, {_format_price_k(guest.get('desired_price_per_night'))}"


def _build_guest_profile_text(guest) -> str:
    categories = "\n".join(
        f"- {html.escape(CATEGORY_MAP.get(c, c))}" for c in guest.preferred_categories
    ) or "- \u041d\u0435\u0442 \u043f\u0440\u0435\u0434\u043f\u043e\u0447\u0438\u0442\u0430\u0435\u043c\u044b\u0445"
    first_name = html.escape(guest.first_name or "")
    last_name = html.escape(guest.last_name or "")
    loyalty = guest.loyalty_status.value.capitalize() if guest.loyalty_status else "-"
    desired_price = guest.desired_price_per_night if guest.desired_price_per_night is not None else "-"
    return (
        "<b>\u041f\u0440\u043e\u0444\u0438\u043b\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f:</b>\n\n"
        f"<b>\u0418\u043c\u044f:</b> {first_name}\n"
        f"<b>\u0424\u0430\u043c\u0438\u043b\u0438\u044f:</b> {last_name}\n\n"
        f"<b>\u0412\u0437\u0440\u043e\u0441\u043b\u044b\u0435:</b> {guest.adults}\n"
        f"<b>\u0414\u0435\u0442\u0438 4-17:</b> {guest.teens}\n"
        f"<b>\u0414\u0435\u0442\u0438 0-3:</b> {guest.infant}\n\n"
        "<b>\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438:</b>\n"
        f"{categories}\n\n"
        f"<b>\u0421\u0442\u0430\u0442\u0443\u0441 \u043b\u043e\u044f\u043b\u044c\u043d\u043e\u0441\u0442\u0438:</b> {loyalty}\n"
        f"<b>\u0416\u0435\u043b\u0430\u0435\u043c\u0430\u044f \u0446\u0435\u043d\u0430:</b> {desired_price} \u0440\u0443\u0431."
    )


def _truncate(text: str, limit: int = 300) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 3]}..."


def _format_log_entry(row) -> str:
    created_at = row.get("created_at")
    ts = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
    level = (row.get("level") or "-").upper()
    source = html.escape(row.get("source") or "-")
    event = html.escape(row.get("event") or "-")
    message = row.get("message") or ""
    message = html.escape(_truncate(message))
    line = f"<b>{ts}</b> [{level}] {source}: {event}"
    if message:
        line = f"{line}\n{message}"
    return line


def _format_logs_text(rows, page: int, total_pages: int) -> str:
    header = (
        f"<b>\u041b\u043e\u0433\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b</b>\n"
        f"\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0430 {page}/{total_pages}\n\n"
    )
    if not rows:
        return f"{header}\u041d\u0435\u0442 \u0441\u043e\u0431\u044b\u0442\u0438\u0439."
    return header + "\n\n".join(_format_log_entry(row) for row in rows)


def _format_admin_notifications_text(rows) -> str:
    header = "<b>\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0430</b>\n\n"
    if not rows:
        return f"{header}\u041d\u0435\u0442 \u043d\u043e\u0432\u044b\u0445 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0439."

    lines = []
    for row in rows:
        created_at = row.get("created_at")
        ts = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
        status = "\u2705" if row.get("acked") else "\U0001F195"
        message = html.escape(row.get("message") or "")
        lines.append(f"{status} {ts}\n{message}")

    return header + "\n\n".join(lines)


async def _send_users_page(message: Message, page: int) -> None:
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        total = repo.count_guests()
        total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * USERS_PER_PAGE
        guests = repo.list_guests(limit=USERS_PER_PAGE, offset=offset)
    rows = [(_format_user_label(g), g["telegram_id"]) for g in guests]
    text = f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438 ({page}/{total_pages}):"
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
    text = f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438 ({page}/{total_pages}):"
    await call.message.edit_text(text, reply_markup=users_list_keyboard(rows, page, total_pages))
    await call.answer()


async def _send_logs_page(message: Message, page: int) -> None:
    with get_connection() as conn:
        ensure_system_event_log_table(conn)
        total = count_events(conn)
        total_pages = max(1, (total + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * LOGS_PER_PAGE
        rows = list_events(conn, limit=LOGS_PER_PAGE, offset=offset)
    text = _format_logs_text(rows, page, total_pages)
    await message.answer(
        text,
        reply_markup=admin_logs_keyboard(page, total_pages),
        parse_mode=ParseMode.HTML,
    )


async def _update_logs_page(call: CallbackQuery, page: int) -> None:
    with get_connection() as conn:
        ensure_system_event_log_table(conn)
        total = count_events(conn)
        total_pages = max(1, (total + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * LOGS_PER_PAGE
        rows = list_events(conn, limit=LOGS_PER_PAGE, offset=offset)
    text = _format_logs_text(rows, page, total_pages)
    await call.message.edit_text(
        text,
        reply_markup=admin_logs_keyboard(page, total_pages),
        parse_mode=ParseMode.HTML,
    )
    await call.answer()


async def _send_admin_notifications(message: Message) -> None:
    with get_connection() as conn:
        ensure_admin_notifications_table(conn)
        rows = list_admin_notifications(conn, limit=10)

    text = _format_admin_notifications_text(rows)
    await message.answer(
        text,
        reply_markup=admin_notifications_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.")
        return
    await message.answer("\u0410\u0434\u043c\u0438\u043d \u043c\u0435\u043d\u044e:", reply_markup=admin_menu_keyboard())


@router.message(F.text == USERS_MENU_TEXT)
async def admin_users(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_users_page(message, page=1)


async def _run_system_job(message: Message, fn, label: str) -> None:
    await message.answer(f"\u0417\u0430\u043f\u0443\u0441\u043a\u0430\u044e: {label}...")
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, fn)
        await message.answer(f"\u0413\u043e\u0442\u043e\u0432\u043e: {label}.")
    except Exception as exc:
        await message.answer(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0437\u0430\u043f\u0443\u0441\u043a\u0435 {label}: {exc}")


@router.message(F.text == NOTIFICATIONS_MENU_TEXT)
async def admin_notifications(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_admin_notifications(message)


@router.message(F.text == LOGS_MENU_TEXT)
async def admin_logs(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_logs_page(message, page=1)


@router.message(F.text == SYSTEM_MENU_TEXT)
async def admin_system_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("\u0421\u0438\u0441\u0442\u0435\u043c\u0430:", reply_markup=admin_system_keyboard())


@router.message(F.text == SYSTEM_ACTION_PRICE_PARSER)
async def admin_run_price_parser(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _run_system_job(message, run_price_parser.run, SYSTEM_ACTION_PRICE_PARSER)


@router.message(F.text == SYSTEM_ACTION_OFFERS_PARSER)
async def admin_run_offers_parser(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _run_system_job(message, run_offers_parser.run, SYSTEM_ACTION_OFFERS_PARSER)


@router.message(F.text == SYSTEM_ACTION_REPRICE)
async def admin_run_reprice(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _run_system_job(message, run_price_matching.run, SYSTEM_ACTION_REPRICE)


@router.message(F.text == SYSTEM_ACTION_BACK)
async def admin_system_back(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("\u0410\u0434\u043c\u0438\u043d \u043c\u0435\u043d\u044e:", reply_markup=admin_menu_keyboard())


@router.message(F.text == NOTIFICATIONS_BACK_TEXT)
async def admin_notifications_back(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("\u0410\u0434\u043c\u0438\u043d \u043c\u0435\u043d\u044e:", reply_markup=admin_menu_keyboard())


@router.message(F.text.in_(list(ADMIN_MENU_ACTIONS.keys())))
async def admin_menu_action(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer(ADMIN_MENU_ACTIONS[message.text])


@router.callback_query(F.data.startswith("admin_users_page:"))
async def admin_users_page(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.", show_alert=True)
        return
    try:
        page = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b.", show_alert=True)
        return
    await _update_users_page(call, page)


@router.callback_query(F.data == "admin_users_noop")
async def admin_users_noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(F.data.startswith("admin_logs_page:"))
async def admin_logs_page(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.", show_alert=True)
        return
    try:
        page = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b.", show_alert=True)
        return
    await _update_logs_page(call, page)


@router.callback_query(F.data == "admin_logs_noop")
async def admin_logs_noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(F.data.startswith("admin_notif_view:"))
async def admin_notification_view(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.", show_alert=True)
        return
    try:
        _, tg_id_str, _notif_id_str = call.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await call.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f.", show_alert=True)
        return

    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    if guest is None:
        await call.answer("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", show_alert=True)
        return

    await call.message.answer(
        _build_guest_profile_text(guest),
        parse_mode=ParseMode.HTML,
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_notif_ack:"))
async def admin_notification_ack(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.", show_alert=True)
        return
    try:
        _, notif_id_str = call.data.split(":")
        notif_id = int(notif_id_str)
    except (ValueError, IndexError):
        await call.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f.", show_alert=True)
        return

    with get_connection() as conn:
        ensure_admin_notifications_table(conn)
        mark_admin_notification_acked(conn, notif_id)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("\u041f\u0440\u0438\u043d\u044f\u0442\u043e.")


@router.callback_query(F.data.startswith("admin_user:"))
async def admin_user_profile(call: CallbackQuery) -> None:
    if not _is_admin(call.from_user.id):
        await call.answer("\u0412\u044b \u043d\u0435 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440.", show_alert=True)
        return
    try:
        _, tg_id_str, page_str = call.data.split(":")
        tg_id = int(tg_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await call.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f.", show_alert=True)
        return

    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    if guest is None:
        await call.answer("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", show_alert=True)
        return

    await call.message.edit_text(
        _build_guest_profile_text(guest),
        reply_markup=back_to_users_keyboard(page),
        parse_mode=ParseMode.HTML,
    )
    await call.answer()
