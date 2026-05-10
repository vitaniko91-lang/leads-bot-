"""FSM states for owner interactions. See spec §6.4 (edit flow)."""
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    awaiting_text = State()    # bot asked owner for new text
    confirming = State()       # bot showed confirm card
