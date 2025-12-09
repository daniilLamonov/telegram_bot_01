from aiogram.fsm.state import State, StatesGroup

class CheckStates(StatesGroup):
    waiting_for_amount = State()      # Ожидание "сумма ФИО"
    waiting_for_file = State()         # Ожидание фото/файла

class InitStates(StatesGroup):
    waiting_for_name = State()
