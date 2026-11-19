"""Suhbat holatlari (FSM)."""

from aiogram.fsm.state import State, StatesGroup


class TxFlow(StatesGroup):
    waiting_input = State()  # /add dan keyin matn kutilmoqda
    waiting_amount = State()
    waiting_type = State()
    waiting_date = State()
    waiting_duplicate = State()
    waiting_note = State()  # «Nima uchun qilindi?»
    edit_menu = State()
    waiting_merchant = State()
    waiting_category = State()  # «Qaysi turga kiradi?»
    waiting_new_category = State()
    waiting_card = State()  # «Qaysi kartadan?»
    waiting_new_card_last4 = State()
    waiting_new_card_name = State()


class CardFlow(StatesGroup):
    name = State()
    last4 = State()
    network = State()
    bank = State()
    currency = State()


class CategoryFlow(StatesGroup):
    name = State()


class SettingsFlow(StatesGroup):
    timezone = State()
