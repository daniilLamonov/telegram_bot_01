from aiogram.fsm.state import State, StatesGroup


class MassExchange(StatesGroup):
    waiting_rate = State()

class CheckStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_file = State()
    editing_check = State()
    editing_date = State()


class ReconciliationStates(StatesGroup):
    waiting_for_date = State()

class NewsletterStates(StatesGroup):
    waiting_for_text = State()
