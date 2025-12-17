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
from database.repositories import UserRepo
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="help")


def help_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ Чеки", callback_data="help_checks"),
        InlineKeyboardButton(text="📊 Отчеты", callback_data="help_reports"),
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
    return builder

def get_help_main_keyboard():
    builder = help_main_keyboard()
    return builder.as_markup()

def get_super_admin_keyboard():
    builder = help_main_keyboard()
    builder.row(
        InlineKeyboardButton(text="Super Admin", callback_data="help_super_settings"),
    )
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
    await temp_msg(
        message,
        (
            "Бот для учёта чеков.\n\n"
            "Выполните команду /init для начала работы.\n"
            "⚠️ Для корректной работы необходимо назначить бота админом чата!!!"
            "Используйте /help чтобы узнать, что я умею."
        ),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await delete_message(message)
    is_admin = await UserRepo.is_admin(message.from_user.id)
    if message.from_user.id in settings.SUPER_ADMIN_ID:
        await message.answer(
            get_help_main_text(),
            reply_markup=get_super_admin_keyboard(),
            parse_mode="HTML",
        )
    elif is_admin:
        await message.answer(
            get_help_main_text(),
            reply_markup=get_help_main_keyboard(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            get_help_main_text(), reply_markup=get_delete_keyboard(), parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("help_"))
async def process_help_callback(callback: CallbackQuery):
    user_id = callback.from_user.id

    if callback.data == "help_back":
        is_super_admin = user_id in settings.SUPER_ADMIN_ID

        if is_super_admin:
            await callback.message.edit_text(
                get_help_main_text(),
                reply_markup=get_super_admin_keyboard(),
                parse_mode="HTML",
            )
        else:
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
• <code>5 000 Иванов Иван</code>
• <code>3 500,50 Петрова Мария Сергеевна</code>
• <code>1 000</code> (ФИО будет "Не указано")

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
    """,
        "help_deposit": """
📥 <b>Пополнение баланса</b>

<b>/get [сумма]</b> - Пополнение RUB наличными
Пример: /get 5 000

<b>/gets [сумма]</b> - Пополнение USDT
Пример: /gets 5 000
""",
        "help_withdraw": """
📤 <b>Выплата средств</b>

<b>/payr [сумма]</b> - Выплата RUB наличными
Пример: /payr 5 000

<b>/pays [сумма]</b> - Выплата USDT
Пример: /pays 5 000

⚠️ Средства списываются с баланса чата
""",
        "help_exchange": """
🔄 <b>Обмен валюты (с комиссией)</b>

<b>/ch [курс] [сумма_руб]</b>
Обмен RUB → USDT

Пример: /ch 92,5 5 000
(обменять 5 000₽ по курсу 92,5)

Результат: (5 000 / 92,5) - комиссия = 51,89 USDT
""",
        "help_settings": """
⚙️ <b>Настройки чата</b>
Для начала работы:
1.Добавляем бота в рабочий чат и делаем админом
 "⚠️ Для корректной работы необходимо назначить бота админом чата!!!"
2. Инициализируем чат
<b>/init [Название]</b>
Инициализировать чат
• Устанавливает название контрагента
• Активирует чат для работы
• Обязательно для первого запуска

<b>/reinit [Название]</b>
Изменить название контрагента
Перезаписывает текущее название

<b>/new [процент]</b> - Установить комиссию
Пример: /new 2,5
(установить комиссию 2,5%)

⚠️ Комиссия применяется ко всем обменам
""",
        "help_super_settings": """
🔴 <b>Только для СУПЕР админов</b>

<b>/setadmin</b> - Добавить нового админа
Ответьте этой командой на сообщение пользователя

<b>/removeadmin</b> - Удалить админа
Ответьте этой командой на сообщение пользователя

<b>/exportall [date1] [date2]</b> - Выгрузить Excel
Полный отчет по ВСЕМ чатам (КА)
Если даты указаны, то за период

⚠️ Эти команды доступны только супер-администраторам
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
