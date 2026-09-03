from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard
from utils.permissions import has_admin_access, is_super_admin

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
            "Для начала работы администратор чата должен выполнить "
            "/init &lt;название КА&gt;.\n"
            "Супер-администратор из конфигурации может выполнить /init "
            "без отдельного назначения.\n\n"
            "⚠️ Для корректной работы необходимо назначить бота админом чата.\n"
            "Используйте /help чтобы узнать, что я умею."
        ),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await delete_message(message)
    if is_super_admin(message.from_user.id):
        await message.answer(
            get_help_main_text(),
            reply_markup=get_super_admin_keyboard(),
            parse_mode="HTML",
        )
    elif await has_admin_access(message.from_user.id):
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
        user_is_super_admin = is_super_admin(user_id)

        if user_is_super_admin:
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
2. Бот попросит отправить фото/документы
3. Для каждого файла укажите сумму и ФИО

<b>Примеры:</b>
• <code>5 000 Иванов Иван</code>
• <code>3 500,50 Петрова Мария Сергеевна</code>
• <code>1 000</code> (ФИО будет "Не указано")

<b>Просмотр чека:</b>
<code>/hcheck [ID чека]</code>
Пример: <code>/hcheck a1b2c3d4</code>
• Показывает фото/документ чека
• Кнопки: "Редактировать", "Другая дата"

<b>Редактирование чека:</b>
1. Откройте чек через <code>/hcheck [ID]</code>
2. Нажмите "Редактировать"
3. Введите новую сумму и ФИО
Формат: <code>сумма ФИО</code> или <code>сумма</code>

<b>Изменение даты чека:</b>
1. Откройте чек через <code>/hcheck [ID]</code>
2. Нажмите "Другая дата"
3. Введите дату в формате: <code>ДД.ММ.ГГГГ</code>
Пример: <code>12.01.2026</code>

<b>Удаление чека:</b>
<code>/del [ID чека]</code> или <code>/delete [ID чека]</code>
Пример: <code>/del a1b2c3d4</code>
⚠️ Требует подтверждения, баланс корректируется автоматически

<b>/sv</b> — Сверка чеков
Интерактивный режим выбора периода:
• Сегодня
• Вчера
• Ввести дату вручную (формат: <code>ДД.ММ.ГГГГ</code>)

Показывает все чеки за выбранный период
с детализацией по каждому
    """,
        "help_reports": """
📊 <b>Отчеты и история</b>

<b>/bal</b> - Текущий баланс чата
Показывает RUB и USDT, комиссию
ℹ️ Каждый чат имеет собственный баланс

<b>/history</b> или <b>/h</b> - Последние 10 операций
Показывает все операции кроме добавления чеков
• Тип операции
• Сумма и валюта
• Курс (если есть)
• Время и пользователь

<b>/hcheck [ID чека]</b> - Просмотр чека по ID
Показывает фото/документ и детали операции

<b>/nb</b> - Статистика на сегодня
Показывает количество обработанных чеков
и общую сумму за сегодняшний день

<b>/export [date1] [date2]</b> - Выгрузить Excel
Полный отчет по операциям данного чата (КА)
• Если даты указаны - за период
• Если не указаны - за всё время
Формат дат: <code>ДД.ММ.ГГГГ</code>
Пример: <code>/export 11.01.2026 12.01.2026</code>
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

<b>/pays [сумма]</b> - Выплата USDT
Пример: <code>/pays 5 000</code>

⚠️ Средства списываются с баланса чата
Проверяется достаточность средств перед списанием
    """,
        "help_exchange": """
🔄 <b>Обмен валюты (с комиссией)</b>

<b>/ch [курс] [сумма_руб]</b>
Обмен RUB → USDT

Пример: <code>/ch 92,5 5 000</code>
(обменять 5 000₽ по курсу 92,5)

Формула расчета:
• USDT = (сумма_руб / курс) - комиссия
• Комиссия берется из настроек чата (команда /new)

Пример результата:
• Списано: 5 000 ₽
• Курс: 92,5
• Комиссия: 2,5% (например)
• Получено: ~51,89 USDT

⚠️ Проверяется достаточность RUB на балансе
    """,
        "help_settings": """
⚙️ <b>Настройки чата</b>
Для начала работы:
1. Добавьте бота в рабочий чат и назначьте его администратором.
2. Инициализируйте чат от имени администратора.
Супер-администратор из конфигурации бота уже обладает этим правом.

<b>/init [Название]</b>
Инициализировать чат
• Создает баланс контрагента
• Активирует чат для работы
• Если баланс КА уже есть, то привязывает чат к нему

<b>/reinit [Название]</b>
Изменить баланс, привязать чат к новому КА
Перезаписывает текущее название

<b>/new [процент]</b> - Установить комиссию
Пример: /new 2,5
(установить комиссию 2,5%)

⚠️ Комиссия применяется ко всем обменам
""",
        "help_super_settings": """
🔴 <b>Только для СУПЕР админов</b>

<b>Управление администраторами:</b>
<b>/setadmin</b> - Добавить нового админа
Ответьте этой командой на сообщение пользователя

<b>/removeadmin</b> - Удалить админа
Ответьте этой командой на сообщение пользователя
⚠️ Нельзя лишить прав суперадмина

<b>Рассылка:</b>
<b>/newsletter</b> - Новостная рассылка
Рассылает сообщение по всем активным чатам
Поддерживает HTML форматирование

<b>Массовый обмен:</b>
<b>/gen</b> - Назначить чат админ-чатом
(будет приходить рассылка при массовых обменах)

<b>/delgen</b> - Убрать чат из админ-чатов

<b>Управление QR:</b>
<b>/setqr</b> - Выбрать Р/С для генерации QR
<b>/stopqr</b> - Временно выключить команду /qr
<b>/startqr</b> - Включить команду /qr

<b>/rate [date]</b> - Указать курс
При использовании команды с датой бот попросит указать
курс и установит его на выбранную дату.

<b>/chall [date1]</b> - Массовый обмен
Обменивает все чеки за указанный период у всех КА
• Каждый КА обменивается по своей комиссии
• Используется указанный курс (запрашивается после команды)
• Формат даты: <code>ДД.ММ.ГГГГ</code>
Пример: <code>/chall 11.01.2026 12.01.2026</code>
ВАЖНО: Команду можно и следует использовать в АВТОМАТИЧЕСКОМ режиме:
при вводе <code>/chall</code> без аргументов бот попросит указать курс
за вчера(если он не был указан ранее командой /rate) и совершит обмен
всех чеков за вчера(если сегодня ВТ-ПТ) или за последние три дня(если сегодня ПН)
по указанному курсу, и за прошлые дни, если чеки были добавлены позже, по курсу,
который был выбран в ранние дни или установлен вручную командой /rate на те
или иные даты.
⚠️ Нельзя обменивать чеки за сегодня

<b>Отчеты:</b>
<b>/exportall [date1] [date2]</b> - Выгрузить Excel
Полный отчет по ВСЕМ чатам (КА)
• Если даты указаны - за период
• Если не указаны - за всё время
• Допускается ввести один конкретный день
Формат дат: <code>ДД.ММ.ГГГГ</code>

<b>/load-check [date1] [date2]</b> - Выгрузить чеки
Присылает zip-архив с фото/документами чеков за период
• Дата берется из записи чека в базе, а не из файла:
  если дату меняли через "Другая дата", чек попадет
  в выгрузку за новую дату
• Если даты не указаны - за сегодня
• Можно указать один день или период
• Если чеков много, архив придет несколькими частями
• Если файл чека не найден на сервере, бот укажет
  ID таких операций
Формат дат: <code>ДД.ММ.ГГГГ</code>
Примеры: <code>/load-check 01.09.2026</code>
<code>/load-check 20.08.2026 29.08.2026</code>

<b>/r</b> - Дневной отчет
Показывает количество чеков и сумму за сегодня
по всем контрагентам с сортировкой по сумме

<b>Сравнение данных:</b>
<b>/compare [date]</b> - Сравнить
Сравнивает txt файл операций с чеками в БД
• Если дата указана - сравнивает за эту дату
• Если не указана - берет сегодняшнюю
• Формат даты: <code>ДД.ММ.ГГГГ</code>
• После команды нужно отправить .txt файл
• Если найдены расхождения - создается Excel отчет

<b>/compare_exl [date]</b> - Сравнить Excel
Сравнивает Excel файл операций с чеками в БД
• Если дата указана - сравнивает за эту дату
• Если не указана - берет сегодняшнюю
• Формат даты: <code>ДД.ММ.ГГГГ</code>
• После команды нужно отправить .txt файл
• Если найдены расхождения - создается Excel отчет

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
