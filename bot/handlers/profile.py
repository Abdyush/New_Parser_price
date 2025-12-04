from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from infrastructure.db.common_db import get_connection
from infrastructure.db.postgres_guest_details_repo import PostgresGuestRepository
from bot.states.registration import Registration
from bot.keyboards.main_menu_kb import main_menu_keyboard
from bot.keyboards.categories_kb import categories_keyboard, CATEGORY_MAP, CATEGORY_REVERSE
from bot.keyboards.loyalty_kb import loyalty_keyboard

router = Router()

@router.message(Command("profile"))
async def show_profile(message: Message):
    tg_id = message.from_user.id

    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    if guest is None:
        await message.answer("Похоже, вы еще не зарегистрированы.\nВведите /start чтобы начать регистрацию.")
        return

    text = (
        "Ваши данные:\n\n"
        f"Имя: {guest.first_name}\n"
        f"Фамилия: {guest.last_name}\n\n"
        f"Взрослых: {guest.adults}\n"
        f"Детей 4–17: {guest.teens}\n"
        f"Детей 0–3: {guest.infant}\n\n"
        "Категории:\n" +
        "\n".join(f"• {CATEGORY_MAP.get(c, c)}" for c in guest.preferred_categories) +
        "\n\n"
        f"Статус лояльности: {guest.loyalty_status.value.capitalize()}\n"
        f"Желаемая цена: {guest.desired_price_per_night} ₽\n"
    )

    await message.answer(text, reply_markup=main_menu_keyboard())
    
    
@router.callback_query(F.data == "wait_ok")
async def wait_ok(call: CallbackQuery):
    tg_id = call.from_user.id

    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        repo.set_active(tg_id, True)

    await call.answer("Уведомления включены!")
    await call.message.answer("Отлично! Я буду присылать уведомления 😊")
    
    
@router.callback_query(F.data == "edit")
async def edit_data(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("Давай обновим информацию. Как тебя зовут?")
    await state.set_state(Registration.waiting_for_first_name)
    await call.answer()
    
    
@router.callback_query(F.data == "edit_categories")
async def edit_categories(call: CallbackQuery, state: FSMContext):
    tg_id = call.from_user.id
    with get_connection() as conn:
        repo = PostgresGuestRepository(conn)
        guest = repo.get_by_telegram_id(tg_id)

    text = (
        "Твои категории:\n\n" +
        "\n".join(f"• {c}" for c in guest.preferred_categories) +
        "\n\nХочешь изменить?"
    )

    # переводим сохранённые названия в ключи для клавиатуры
    selected_keys = []
    for cat in guest.preferred_categories:
        if cat in CATEGORY_REVERSE:
            selected_keys.append(CATEGORY_REVERSE[cat])
        elif cat in CATEGORY_REVERSE.values():  # уже ключи
            selected_keys.append(cat)

    # повторяем клавиатуру выбора категорий
    await state.update_data(
        preferred_categories=list(selected_keys),
        editing_categories=True,
    )
    await state.set_state(Registration.choosing_categories)
    await call.message.answer(text, reply_markup=categories_keyboard(selected=selected_keys))
    await call.answer()
    
    
@router.callback_query(F.data == "edit_price")
async def edit_price(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(editing_price=True)
    await call.message.answer("Введите новую желаемую стоимость:")
    await state.set_state(Registration.desired_price)
    await call.answer()
    
    
@router.callback_query(F.data == "edit_status")
async def edit_status(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(editing_status=True)
    await call.message.answer("Выберите новый статус:", reply_markup=loyalty_keyboard())
    await state.set_state(Registration.loyalty)
    await call.answer()
