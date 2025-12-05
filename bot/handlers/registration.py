from aiogram import Router
from aiogram.enums import ParseMode
import html
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
from aiogram import F
from aiogram.types import CallbackQuery
from core.entities import GuestDetails, LoyaltyStatus
from bot.states.registration import Registration
from bot.keyboards.categories_kb import categories_keyboard, CATEGORY_MAP, CATEGORY_REVERSE
from bot.keyboards.loyalty_kb import loyalty_keyboard
from infrastructure.db.postgres_guest_details_repo import PostgresGuestRepository
from infrastructure.db.common_db import get_connection
from bot.keyboards.main_menu_kb import main_menu_keyboard


def _categories_text(selected: list[str], editing: bool) -> str:
    """Формирует текст с выбранными категориями."""
    pretty = "\n".join(f"• {CATEGORY_MAP.get(c, c)}" for c in selected) or "• Пока ничего не выбрано"
    if editing:
        return "Твои категории:\n\n" + pretty + "\n\nХочешь изменить?"
    return "Выбранные категории:\n\n" + pretty


def guest_summary(guest) -> str:
    categories = "\n".join(
        f"• {html.escape(CATEGORY_MAP.get(c, c))}" for c in guest.preferred_categories
    )
    return (
        "📌 <b>Ваши текущие данные:</b>\n\n"
        f"<b>Имя:</b> {html.escape(guest.first_name)}\n"
        f"<b>Фамилия:</b> {html.escape(guest.last_name)}\n\n"
        f"<b>Взрослых:</b> {guest.adults}\n"
        f"<b>Детей 4–17:</b> {guest.teens}\n"
        f"<b>Детей 0–3:</b> {guest.infant}\n\n"
        "<b>Категории:</b>\n" + categories + "\n\n"
        f"<b>Статус:</b> {html.escape(guest.loyalty_status.value.capitalize())}\n"
        f"<b>Желаемая цена:</b> {guest.desired_price_per_night} ₽"
    )


router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()  # чтобы не остаться в старом FSM

    tg_id = message.from_user.id

    # Проверяем БД
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    if guest:
        # Формируем красивый вывод
        await message.answer(
            guest_summary(guest),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    # Если данных нет → запускаем регистрацию
    await message.answer(
        "Привет! Давай заполним твою анкету 😊\n\nКак тебя зовут?"
    )
    await state.set_state(Registration.waiting_for_first_name)
    

@router.message(F.text == "Редактировать данные")
async def edit_profile(message: Message, state: FSMContext):
    await message.answer("Давай обновим твои данные! Введи своё имя:", reply_markup=None)
    await state.set_state(Registration.waiting_for_first_name)


# 1️⃣ — Получаем имя
@router.message(Registration.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    first_name = message.text.strip()

    if not first_name or len(first_name) < 2:
        await message.answer("Имя должно содержать минимум 2 символа. Попробуем ещё раз?")
        return

    await state.update_data(first_name=first_name)

    await message.answer("Отлично! Теперь введи свою фамилию:")
    await state.set_state(Registration.waiting_for_last_name)


# 2️⃣ — Получаем фамилию
@router.message(Registration.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    last_name = message.text.strip()

    if not last_name or len(last_name) < 2:
        await message.answer("Фамилия должна содержать минимум 2 символа. Введи ещё раз:")
        return

    await state.update_data(last_name=last_name)

    await message.answer("Сколько взрослых обычно путешествуют с тобой?")
    await state.set_state(Registration.waiting_for_adults)


# 3️⃣ — Получаем количество взрослых
@router.message(Registration.waiting_for_adults)
async def process_adults(message: Message, state: FSMContext):
    try:
        adults = int(message.text)
        if adults < 1 or adults > 10:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 10.")
        return

    await state.update_data(adults=adults)

    await message.answer("Сколько детей в возрасте 4–17 лет?")
    await state.set_state(Registration.waiting_for_teens)


# 4️⃣ — Получаем количество детей 4–17 (teens)
@router.message(Registration.waiting_for_teens)
async def process_teens(message: Message, state: FSMContext):
    try:
        teens = int(message.text)
        if teens < 0 or teens > 10:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 0 до 10.")
        return

    await state.update_data(teens=teens)

    await message.answer("Сколько малышей 0–3 лет?")
    await state.set_state(Registration.waiting_for_infants)


# После infants → сразу категориями
@router.message(Registration.waiting_for_infants)
async def process_infants(message: Message, state: FSMContext):

    try:
        infant = int(message.text)
        if infant < 0 or infant > 10:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 0 до 10.")
        return

    await state.update_data(infant=infant)
    await state.update_data(preferred_categories=[])

    await message.answer(
        "Отлично! Теперь выбери категории номеров.\n"
        "Можно выбрать несколько.\n"
        "Когда закончишь — нажми «📌 Подтвердить».",
        reply_markup=categories_keyboard([])
    )

    await state.set_state(Registration.choosing_categories)



@router.callback_query(Registration.choosing_categories, F.data.startswith("cat:"))
async def select_category(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":")[1]

    data = await state.get_data()
    selected = data.get("preferred_categories", [])

    # завершить
    if action == "done":
        if not selected:
            await call.answer("Вы не выбрали ни одной категории!")
            return

        selected_titles = [CATEGORY_MAP[k] for k in selected]
        await call.message.answer(
            "Вы выбрали:\n" + "\n".join(f"• {x}" for x in selected_titles)
        )
        await call.answer()
        # переход к следующему шагу
        return

    # добавление/удаление категории (toggle)
    if action not in selected:
        selected.append(action)
        await state.update_data(preferred_categories=selected)
        await call.answer(f"Добавлено: {CATEGORY_MAP[action]}")
    else:
        selected.remove(action)
        await state.update_data(preferred_categories=selected)
        await call.answer(f"Удалено: {CATEGORY_MAP[action]}")

    # Обновляем текст списка для наглядности
    await call.message.edit_text(
        _categories_text(selected, editing=data.get("editing_categories", False)),
        reply_markup=categories_keyboard(selected)
    )



# 👉 Подтверждение
@router.callback_query(Registration.choosing_categories, F.data == "cat_done")
async def categories_done(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    selected = data.get("preferred_categories", [])
    selected_titles = [CATEGORY_MAP.get(k, k) for k in selected]

    if not selected:
        await call.answer("Выберите хотя бы одну категорию")
        return

    # Если редактируем из профиля — сохраняем только категории и завершаем
    if data.get("editing_categories"):
        with get_connection() as conn:
            repo = PostgresGuestRepository(conn)
            guest = repo.get_by_telegram_id(call.from_user.id)
            if guest:
                guest.preferred_categories = selected_titles
                repo.save_guest(guest)

        if guest is None:
            await call.message.answer("Профиль не найден, попробуйте /start", reply_markup=main_menu_keyboard())
            await state.clear()
            await call.answer()
            return

        # Показываем обновленную анкету тем же текстом, что и в меню профиля
        await call.message.answer(
            guest_summary(guest),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        await call.answer()
        return

    await call.message.answer(
        "Вы выбрали:\n" +
        "\n".join(f"• {c}" for c in selected_titles)
    )

    # Переход к выбору статуса лояльности
    await call.message.answer(
        "Теперь выбери свой статус по программе лояльности:",
        reply_markup=loyalty_keyboard()
    )
    await state.set_state(Registration.loyalty)
    await call.answer()
    
    
@router.callback_query(Registration.loyalty, F.data.startswith("loy_"))
async def select_loyalty(call: CallbackQuery, state: FSMContext):
    status = call.data[4:]  # удаляем "loy_"

    await state.update_data(loyalty_status=status)

    # Обновляем клавиатуру и показываем выбранный статус
    await call.message.edit_reply_markup(
        reply_markup=loyalty_keyboard(selected=status)
    )

    await call.answer(f"Вы выбрали: {status}")
   
    
@router.callback_query(Registration.loyalty, F.data == "loyalty_cancel")
async def loyalty_cancel(call: CallbackQuery, state: FSMContext):
    await state.update_data(loyalty_status=None)

    await call.message.edit_reply_markup(
        reply_markup=loyalty_keyboard(selected=None)
    )
    await call.answer("Выбор сброшен!")
    
    
@router.callback_query(Registration.loyalty, F.data == "loyalty_done")
async def loyalty_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    status = data.get("loyalty_status")

    if not status:
        await call.answer("Выберите статус перед подтверждением!")
        return

    # Если меняем статус в уже существующей анкете
    if data.get("editing_status"):
        with get_connection() as conn:
            repo = PostgresGuestRepository(conn)
            guest = repo.get_by_telegram_id(call.from_user.id)

            if guest is None:
                await call.message.answer("Профиль не найден, попробуйте /start", reply_markup=main_menu_keyboard())
                await state.clear()
                await call.answer()
                return

            guest.loyalty_status = LoyaltyStatus(status.lower())
            repo.save_guest(guest)

        await call.message.answer(
            guest_summary(guest),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        await call.answer()
        return

    await call.message.answer(f"Отлично! Ваш статус: {status}")

    # Переход к следующему шагу — желаемой цене
    await call.message.answer("Теперь укажите желаемую стоимость за ночь:")
    await state.set_state(Registration.desired_price)

    await call.answer()
    
    
@router.message(Registration.desired_price)
async def process_desired_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        if price < 1000 or price > 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer("Введите число — желаемую стоимость (например 25000).")
        return

    await state.update_data(desired_price_per_night=price)

    data = await state.get_data()
    categories_titles = [CATEGORY_MAP.get(k, k) for k in data.get("preferred_categories", [])]

    if data.get("editing_price"):
        with get_connection() as conn:
            repo = PostgresGuestRepository(conn)
            guest = repo.get_by_telegram_id(message.from_user.id)

            if guest is None:
                await message.answer("Профиль не найден, попробуйте /start", reply_markup=main_menu_keyboard())
                await state.clear()
                return

            guest.desired_price_per_night = price
            repo.save_guest(guest)

        await message.answer("Стоимость обновлена. Вот актуальные данные:")
        await message.answer(
            guest_summary(guest),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await state.clear()
        return

    await message.answer("Отлично! Сохраняю твою анкету…")

    # ⚡ СОБИРАЕМ ОБЪЕКТ GuestDetails
    guest = GuestDetails(
        id=None,
        telegram_id=message.from_user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        adults=data["adults"],
        teens=data["teens"],
        infant=data["infant"],
        preferred_categories=categories_titles,
        loyalty_status=LoyaltyStatus(data["loyalty_status"].lower()),
        desired_price_per_night=data["desired_price_per_night"],
        created_at=datetime.now()
    )
    
    # ⚡ СОХРАНЕНИЕ В БД
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        repo.save_guest(guest)

    await message.answer("Анкета успешно сохранена! 🎉")
    
    # 📌 Формируем красивое резюме данных
    text = (
        "Регистрация завершена! 🎉\n\n"
        f"Имя: {guest.first_name}\n"
        f"Фамилия: {guest.last_name}\n\n"
        f"Взрослых: {guest.adults}\n"
        f"Детей 4–17: {guest.teens}\n"
        f"Детей 0–3: {guest.infant}\n\n"
        "Категории:\n" +
        "".join(f"• {c}\n" for c in guest.preferred_categories) +
        f"\nСтатус лояльности: {guest.loyalty_status.name.capitalize()}\n"
        f"Желаемая цена: {guest.desired_price_per_night} ₽"
    )

    await message.answer(text)
    await state.clear()
    await message.answer("Готово! Чем займемся дальше?", reply_markup=main_menu_keyboard())
  
    

    

    
    
