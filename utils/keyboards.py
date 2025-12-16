from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_delete_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Скрыть", callback_data="delete_message")
    return builder.as_markup()
