from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_adults = State()
    waiting_for_teens = State()
    waiting_for_infants = State()
    choosing_categories = State()
    loyalty = State()   
    desired_price = State()
    finished = State()
    