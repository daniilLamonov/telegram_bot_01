from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="help")


def get_help_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ Чеки", callback_data="help_checks"),
        InlineKeyboardButton(text="📊 Отчеты", callback_data="help_reports")
    )
    builder.row(

        InlineKeyboardButton(text="💰 Пополнение", callback_data="help_deposit"),
        InlineKeyboardButton(text="📤 Выплата", callback_data="help_withdraw"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обмен", callback_data="help_exchange"),
        InlineKeyboardButton(text="⚙️ Администрирование", callback_data="help_settings"),
    )

    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="delete_message"))
    return builder.as_markup()


def get_help_main_text():
    return """
📖 <b>Справка по командам бота</b>

<b>📸 Быстро добавить Чек:</b>/check [сумма] ФИО + фото

<b>📊 Сверка чеков по датам:</b> /sv

<i>Выберите категорию для подробной информации ⬇️</i>
"""

@router.message(Command("start"))
async def cmd_start(message: Message):
    await delete_message(message)
    is_admin = message.from_user.id in settings.ADMIN_IDS
    chat_type = message.chat.type

    if chat_type == "private":
        if is_admin:
            greeting = (
                "👋 <b>Привет, администратор!</b>\n\n"
                "Этот бот предназначен для работы в групповых чатах.\n\n"
                "Добавьте меня в группу и выполните команду /init для начала работы.\n\n"
                "Используйте /help для списка доступных команд."
            )
        else:
            greeting = (
                "👋 <b>Привет!</b>\n\n"
                "Этот бот работает только в групповых чатах.\n\n"
            )
    else:
        greeting = (
            f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
            "Я бот для учёта чеков.\n\n"
            "Выполните команду /init для начала работы.\n"
            "Используйте /help чтобы узнать, что я умею."
        )

    await temp_msg(message, greeting, parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    await delete_message(message)
    is_admin = message.from_user.id in settings.ADMIN_IDS
    if is_admin:
        await message.answer(
            get_help_main_text(), reply_markup=get_help_main_keyboard(), parse_mode="HTML"
        )
    else:
        await message.answer(
            get_help_main_text(), reply_markup=get_delete_keyboard(), parse_mode="HTML"
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
        "help_checks": """
    📎 <b>Работа с чеками</b>

    <b>Добавление чека:</b>
    СПОСОБ А:
    1. Отправьте фото или документ чека
    2. Бот попросит указать сумму и плательщика
    3. Введите данные в формате: <code>сумма ФИО</code>
    
    СПОСОБ Б:
    Быстро добавить Чек: <code>/check</code> [сумма] ФИО + фото
    
    СПОСОБ В:
    1. Написать команду <code>/check</code>
    2. Бот попросит указать сумму и плательщика
    3. Введите данные в формате: <code>сумма ФИО</code>

    <b>Примеры:</b>
    • <code>5000 Иванов Иван</code>
    • <code>3500.50 Петрова Мария Сергеевна</code>
    • <code>1000</code> (ФИО будет "Не указано")

    <b>Удаление чека:</b>
    <code>/del [ID чека]</code>
    Пример: <code>/del a1b2c3d4</code>

    <b>Просмотр чека:</b>
    <code>/hcheck [ID чека]</code>
    Пример: <code>/hcheck a1b2c3d4</code>
    
    <b>/sv</b> — Сверка чеков
    Интерактивный режим выбора периода:
    • Сегодня
    • Вчера
    • Ввести дату вручную
    
    Показывает все чеки за выбранный период
    с детализацией по каждому
    
    <b>Формат истории:</b>
    📅 [Дата время]
    💳 Операция: [тип]
    💰 Сумма: [сумма]
    🆔 ID: [идентификатор]
    👤 Плательщик: [ФИО]
        """,
        "help_reports": """
        📊 <b>Отчеты и история</b>

    <b>/bal</b> - Текущий баланс чата
    Показывает RUB и USDT
    ℹ️ Каждый чат имеет собственный баланс
    
    <b>/history или /h </b> - Покажет последние 10 операций
    Кроме добавления чеков.
    
    <b>/hcheck [id чека] </b> - Покажет чек операции по id
    
    <b>/export [date1] [date2]</b> - Выгрузить Excel
    Полный отчет по операциям данного чата(КА)
    (если даты указана, то за период)
    
    <b>/exportall [date1] [date2]</b> - Выгрузить Excel
    Полный отчет по всем чатам(КА) (если даты указана, то за период)
    """,
        "help_deposit": """
    📥 <b>Пополнение баланса</b>
    
    <b>/get [сумма]</b> - Пополнение RUB наличными
    Пример: /get 5000
    
    <b>/gets [сумма]</b> - Пополнение USDT
    Пример: /gets 100
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
    🔄 <b>Обмен валюты (с коммисией)</b>
    
    <b>/ch [курс] [сумма_руб]</b>
    Обмен RUB → USDT
    
    Пример: /ch 92.5 10000
    (обменять 10000₽ по курсу 92.5)
    
    Результат: (10000 - коммисия) / 92.5 = 108.11 USDT
""",
        "help_settings": """
    ⚙️ <b>Настройки чата</b>
    <b>/init</b>
    Инициализировать чат
    • Устанавливает название контрагента
    • Активирует чат для работы
    • Обязательно для первого запуска

    <b>/reinit</b>
    Изменить название контрагента
    Перезаписывает текущее название

    <b>/new [процент]</b> - Установить комиссию
    Пример: /new 2.5
    (установить комиссию 2.5%)

    ⚠️ Комиссия применяется ко всем обменам
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
