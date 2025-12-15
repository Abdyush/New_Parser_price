from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from infrastructure.db.common_db import get_connection
from app.notifications.service import (
    CategoryNotification,
    load_offers_for_guest,
    filter_offers_by_preferences,
    load_parser_status,
)
from app.notifications.notifier import send_notifications
from bot.keyboards.notifications_kb import (
    notifications_keyboard,
    notification_details_keyboard,
)

def _best_price(cat: CategoryNotification) -> float:
    best = float("inf")
    for item in cat.items:
        for val in (item.new_breakfast_price, item.new_full_pansion_price):
            if val is not None:
                best = min(best, val)
    return best


def _parse_date(raw: str):
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _format_date_str(raw: str) -> str:
    dt = _parse_date(raw)
    return dt.strftime("%d.%m.%y") if dt else raw


def _format_period(period: str) -> str:
    try:
        clean = period.replace(" ", "")
        parts = clean.split("-")
        if len(parts) >= 6:
            start_raw = "-".join(parts[:3])
            end_raw = "-".join(parts[3:6])
        else:
            start_raw, end_raw = clean.split("-", 1)
        start = _parse_date(start_raw)
        end = _parse_date(end_raw)
        if start and end:
            return f"{start:%d.%m.%y} - {end:%d.%m.%y}"
    except Exception:
        pass
    return period


def _format_last_rooms(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw = str(value).replace(";", ",")
        raw = raw.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        raw_items = raw.split(",")

    formatted = []
    for item in raw_items:
        part = item.strip()
        if not part:
            continue
        formatted.append(_format_date_str(part))

    return ", ".join(formatted) if formatted else None


async def _send_user_offers(bot, chat_id: int, user_id: int):
    parser_status = None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, first_name FROM guest_details WHERE telegram_id = %s",
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            await bot.send_message(chat_id, "Похоже, вы ещё не зарегистрированы. Нажмите /start для регистрации.")
            return

        guest_id, first_name = row
        offers = filter_offers_by_preferences(conn, guest_id, load_offers_for_guest(conn, guest_id))
        parser_status = load_parser_status(conn)

    if not offers:
        await bot.send_message(chat_id, "На данный момент, в отеле нет номеров удовлетворяющих Вашим требованиям")
        return

    warning = ""
    if parser_status and parser_status.status != "ok":
        failed_at = _format_date_str(parser_status.failed_at.isoformat()) if parser_status.failed_at else "неизвестной дате"
        warn_msg = parser_status.message or f"Парсер собрал не все данные, сломался на дате {failed_at}."
        warning = f"⚠️ {warn_msg}\n\n"

    text = warning + (
        f"Здравствуйте, {first_name}!\n\n"
        "Ниже подборка категорий, подходящих под ваши параметры. "
        "Выберите вариант, чтобы посмотреть детали."
    )
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=notifications_keyboard(guest_id, offers)
    )


router = Router()


# Вспомогательная команда: посмотреть свои актуальные категории вручную
@router.message(F.text == "/my_offers")
async def cmd_my_offers(message: Message):
    await _send_user_offers(message.bot, message.chat.id, message.from_user.id)

@router.message(F.text == "/send_notifications")
async def cmd_send_notifications(message: Message):
    await send_notifications(message.bot)


# Нажатие на конкретную категорию – показать детали
@router.callback_query(F.data == "show_available")
async def on_show_available(call: CallbackQuery):
    await _send_user_offers(call.bot, call.message.chat.id, call.from_user.id)
    await call.answer()


@router.callback_query(F.data.startswith("n_it_"))
async def on_notification_item(call: CallbackQuery):
    payload = call.data.replace("n_it_", "", 1)
    guest_id_str, idx_str = payload.split("_", 1)
    guest_id = int(guest_id_str)
    idx = int(idx_str)

    with get_connection() as conn:
        categories = sorted(
            filter_offers_by_preferences(conn, guest_id, load_offers_for_guest(conn, guest_id)),
            key=_best_price
        )
        if not categories or idx >= len(categories):
            await call.answer("Не удалось найти данные по этой категории.", show_alert=True)
            return
        category = categories[idx]

    lines = [f"<b>{category.category}</b>"]

    max_items = 10
    total_items = len(category.items)

    for item in category.items[:max_items]:
        lines.append(f"\nПериод: {_format_period(item.period)}")
        lines.append("💰 <b>Завтрак:</b>")
        lines.append(f"• обычная: {item.regular_breakfast_price} ₽")
        lines.append(f"• со скидками: {item.new_breakfast_price} ₽")
        lines.append("🍽 <b>Полный пансион:</b>")
        lines.append(f"• обычная: {item.regular_full_pansion_price} ₽")
        lines.append(f"• со скидками: {item.new_full_pansion_price} ₽")

        if item.applied_special_offer_title:
            suffix = f", мин. ночей: {item.applied_special_offer_min_days}" if item.applied_special_offer_min_days else ""
            lines.append(f"🎁 {item.applied_special_offer_title}{suffix}")
        if item.applied_special_offer_text:
            lines.append(f"Текст специального предложения: {item.applied_special_offer_text}")

        if item.applied_loyalty:
            lines.append(
                f"💎 Лояльность: {item.applied_loyalty} ({item.loyalty_discount_percent}% скидка)"
            )

        if item.formula_used:
            lines.append(f"🧮 Формула: {item.formula_used}")

        last_rooms = _format_last_rooms(item.is_last_room)
        if last_rooms:
            lines.append(f"Последние номера: {last_rooms}")

    if total_items > max_items:
        lines.append(f"\nПоказаны первые {max_items} из {total_items} периодов. Уточните даты или примените фильтр.")

    lines.append(
        "\nСкидки действуют при выполнении условий спецпредложения и наличии баллов/статуса."
    )

    text = "\n".join(lines)

    await call.message.edit_text(
        text,
        reply_markup=notification_details_keyboard(guest_id),
        parse_mode="HTML",
    )
    await call.answer()


# Назад к списку категорий
@router.callback_query(F.data.startswith("n_back_"))
async def on_notifications_back(call: CallbackQuery):
    guest_id = int(call.data.replace("n_back_", ""))

    with get_connection() as conn:
        offers = filter_offers_by_preferences(conn, guest_id, load_offers_for_guest(conn, guest_id))

    if not offers:
        await call.message.edit_text(
            "Сейчас нет категорий, подходящих под желаемую цену."
        )
        await call.answer()
        return

    text = (
        "Давай посмотрим категории, подходящие под Ваш отбор.\n"
        "Чтобы ознакомиться подробнее, нажмите на кнопку с интересующей категорией."
    )
    await call.message.edit_text(
        text,
        reply_markup=notifications_keyboard(guest_id, offers)
    )
    await call.answer()


# Нажатие "Ознакомился, спасибо!"
@router.callback_query(F.data == "n_ack")
async def on_notifications_ack(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Буду держать в курсе! 🙂")
