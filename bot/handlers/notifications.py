from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from infrastructure.db.common_db import get_connection
from app.notifications.service import (
    load_offers_for_guest,
    load_single_offer,
)
from app.notifications.notifier import send_notifications
from bot.keyboards.notifications_kb import (
    notifications_keyboard,
    notification_details_keyboard,
)

router = Router()


# Вспомогательная команда: посмотреть свои актуальные категории вручную
@router.message(F.text == "/my_offers")
async def cmd_my_offers(message: Message):
    user_id = message.from_user.id

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, first_name FROM guest_details WHERE telegram_id = %s",
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            await message.answer("Я не нашёл твою анкету. Нажми /start для регистрации.")
            return

        guest_id, first_name = row
        offers = load_offers_for_guest(conn, guest_id)

    if not offers:
        await message.answer(
            "Сейчас нет категорий, которые подходят под твою желаемую цену."
        )
        return

    text = (
        f"Добрый день, {first_name}!\n\n"
        "Ниже категории, подходящие под Ваш отбор. "
        "Чтобы ознакомиться подробнее, нажмите на кнопку с интересующей категорией."
    )
    await message.answer(
        text,
        reply_markup=notifications_keyboard(guest_id, offers)
    )


@router.message(F.text == "/send_notifications")
async def cmd_send_notifications(message: Message):
    await send_notifications(message.bot)


# Нажатие на конкретную категорию – показать детали
@router.callback_query(F.data.startswith("n_it_"))
async def on_notification_item(call: CallbackQuery):
    guest_price_id = int(call.data.replace("n_it_", ""))

    with get_connection() as conn:
        offer = load_single_offer(conn, guest_price_id)
        if not offer:
            await call.answer("Не удалось найти данные по этому предложению.", show_alert=True)
            return

    # Формируем текст
    lines = []
    lines.append(f"<b>{offer.category}</b>")
    lines.append(f"Период: {offer.period}")
    lines.append("")
    lines.append("💰 <b>Тариф с завтраком:</b>")
    lines.append(f"• обычная цена: {offer.regular_breakfast_price} ₽")
    lines.append(f"• цена со скидками: {offer.new_breakfast_price} ₽")
    lines.append("")
    lines.append("🍽 <b>Полный пансион:</b>")
    lines.append(f"• обычная цена: {offer.regular_full_pansion_price} ₽")
    lines.append(f"• цена со скидками: {offer.new_full_pansion_price} ₽")
    lines.append("")

    if offer.applied_special_offer_title:
        lines.append(f"🎁 Спецпредложение: {offer.applied_special_offer_title}")
        if offer.applied_special_offer_min_days:
            lines.append(f"Минимум ночей по спецпредложению: {offer.applied_special_offer_min_days}")
        lines.append("")

    if offer.applied_loyalty:
        lines.append(
            f"💎 Статус лояльности: {offer.applied_loyalty} "
            f"({offer.loyalty_discount_percent}% скидка)"
        )
        lines.append("")

    if offer.formula_used:
        lines.append(f"Формула, по которой считалась цена: {offer.formula_used}")
        lines.append("")

    lines.append(
        "Данная стоимость применится только если будут соблюдены "
        "условия спецпредложения, и на вашем бонусном счету "
        "достаточно баллов, чтобы в полной мере воспользоваться скидкой."
    )

    text = "\n".join(lines)

    await call.message.edit_text(
        text,
        reply_markup=notification_details_keyboard(offer),
        parse_mode="HTML",
    )
    await call.answer()


# Назад к списку категорий
@router.callback_query(F.data.startswith("n_back_"))
async def on_notifications_back(call: CallbackQuery):
    guest_id = int(call.data.replace("n_back_", ""))

    with get_connection() as conn:
        offers = load_offers_for_guest(conn, guest_id)

    if not offers:
        await call.message.edit_text(
            "Сейчас нет категорий, подходящих под вашу желаемую цену."
        )
        await call.answer()
        return

    # можно получить имя гостя для текста, но не обязательно
    text = (
        "Ниже категории, подходящие под Ваш отбор.\n"
        "Чтобы ознакомиться подробнее, нажмите на кнопку с интересующей категорией."
    )
    await call.message.edit_text(
        text,
        reply_markup=notifications_keyboard(guest_id, offers)
    )
    await call.answer()


# Кнопка "Ознакомился, спасибо!"
@router.callback_query(F.data == "n_ack")
async def on_notifications_ack(call: CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Рад быть полезным! 😊")
