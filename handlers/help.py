from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name="help")


def get_help_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Пополнение", callback_data="help_deposit"),
        InlineKeyboardButton(text="📤 Выплата", callback_data="help_withdraw"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обмен", callback_data="help_exchange"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="help_settings"),
    )
    builder.row(InlineKeyboardButton(text="📊 Отчеты", callback_data="help_reports"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="delete_message"))
    return builder.as_markup()


def get_help_main_text():
    return """
📖 <b>Справка по командам бота</b>
<b>📸 Чек:</b> Имя Фамилия /check [сумма] + фото

<b>💰 Баланс:</b> /bal
<b>📊 История:</b> /history

<i>Выберите категорию для подробной информации ⬇️</i>
"""


@router.message(Command("help"))
async def cmd_help(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        get_help_main_text(), reply_markup=get_help_main_keyboard(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("help_"))
async def process_help_callback(callback: CallbackQuery):
    if callback.data == "help_back":
        await callback.message.edit_text(
            get_help_main_text(),
            reply_markup=get_help_main_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    help_sections = {
        "help_deposit": """
📥 <b>Пополнение баланса</b>

<b>/get [сумма]</b> - Пополнение RUB наличными
Пример: /get 5000

<b>/gets [сумма]</b> - Пополнение USDT
Пример: /gets 100

<b>Фамилия Имя Отчество /check [сумма]</b> + фото/файл
Пополнение по чеку с подтверждением
Пример: Иван Петров /check 3000
(прикрепить фото чека)
""",
        "help_withdraw": """
📤 <b>Выплата средств</b>

<b>/payr [сумма]</b> - Выплата RUB наличными
Пример: /payr 2000

<b>/pays [сумма]</b> - Выплата USDT
Пример: /pays 50

⚠️ Средства списываются с баланса чата
""",
        "help_exchange": """
🔄 <b>Обмен валюты</b>

<b>/ch [курс] [сумма_руб]</b>
Обмен RUB → USDT

Пример: /ch 92.5 10000
(обменять 10000₽ по курсу 92.5)

Результат: 10000 / 92.5 = 108.11 USDT
""",
        "help_settings": """
⚙️ <b>Настройки чата</b>

<b>/init</b> - Инициализация чата
Укажите название контрагента

<b>/del [id операции]</b> - Удалить операцию
Пример: /del 3a43b2ba

<b>/new [процент]</b> - Установить комиссию
Пример: /new 2.5
(установить комиссию 2.5%)

Комиссия применяется ко всем пополнениям
""",
        "help_reports": """
📊 <b>Отчеты и история</b>

<b>/bal</b> - Текущий баланс чата
Показывает RUB и USDT

<b>/history или /h </b> - Покажет последние 10 операций
Кроме добавления чеков.

<b>/hcheck [id чека] </b> - Покажет чек операции по id

<b>/export [date1] [date2]</b> - Выгрузить Excel
Полный отчет по операциям данного чата(КА)
(если даты указана, то за период)

<b>/exportall [date1] [date2]</b> - Выгрузить Excel
Полный отчет по всем чатам(КА) (если даты указана, то за период)
""",
    }

    section_text = help_sections.get(callback.data, "❌ Раздел не найден")

    back_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к меню", callback_data="help_back")]
        ]
    )

    await callback.message.edit_text(
        section_text, reply_markup=back_button, parse_mode="HTML"
    )
    await callback.answer()
