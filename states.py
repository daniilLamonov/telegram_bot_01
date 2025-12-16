from aiogram.fsm.state import State, StatesGroup


class CheckStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_file = State()


class ReconciliationStates(StatesGroup):
    waiting_for_date = State()
