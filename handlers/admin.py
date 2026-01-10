import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.repositories import ChatRepo, UserRepo
from database.repositories.balance_repo import BalanceRepo
from filters.admin import IsAdminFilter
from states import NewsletterStates

from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="admin")


@router.message(Command("new"), IsAdminFilter())
async def cmd_new(message: Message):
    await delete_message(message)
    args = message.text.split()[1:]

    if not args:
        await temp_msg(message, "Использование: /new <процент>")
        return

    try:
        percent = float(args[0].replace(",", "."))
        chat_id = message.chat.id

        balance_id = await ChatRepo.get_balance_id(chat_id)
        if not balance_id:
            await temp_msg(message, "❌ Чат не инициализирован")
            return

        await BalanceRepo.set_commission(balance_id, percent)

        await temp_msg(message, f"✅ Комиссия баланса: {percent:.2f}%")

    except (ValueError, IndexError):
        await temp_msg(message, "❌ Введите корректный процент")


@router.message(Command("init"), IsAdminFilter())
async def cmd_init(message: Message):
    await delete_message(message)

    chat_info = await ChatRepo.get_chat(message.chat.id)
    balance = await BalanceRepo.get_by_chat(message.chat.id)

    if chat_info:
        await temp_msg(
            message,
            f"ℹ️ <b>Чат уже инициализирован</b>\n\n"
            f"📝 Контрагент: <b>{balance['name']}</b>\n"
            f"📅 Инициализирован: {chat_info['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Используйте /reinit для повторной инициализации",
            parse_mode="HTML",
        )
        return

    match = re.search(r"^/init(?:@\w+)?\s+(.+)", message.text)
    if not match:
        await temp_msg(
            message,
            "❌ Требуется ввести название КА.\n" "Пример: <code>/init ABC13 LTD</code>",
            parse_mode="HTML",
        )
        return

    contractor_name = match.group(1).strip()

    balance = await BalanceRepo.get_by_name(contractor_name)
    if not balance:
        balance = await BalanceRepo.create(contractor_name)

    success = await ChatRepo.initialize_chat(
        chat_id=message.chat.id,
        chat_title=message.chat.title or "",
        chat_type=message.chat.type,
        initialized_by=message.from_user.id,
        balance_id=balance['id'],
    )

    if success:
        await temp_msg(
            message,
            f"✅ <b>Чат инициализирован!</b>\n\n"
            f"📝 Контрагент: <b>{contractor_name}</b>\n"
            f"🆔 Баланс ID: <code>{balance['id']}</code>\n"
            f"💵 RUB: <code>{balance['balance_rub']:.2f}</code>\n"
            f"💰 USDT: <code>{balance['balance_usdt']:.8f}</code>",
            parse_mode="HTML",
        )
    else:
        await temp_msg(message, "❌ Ошибка при инициализации чата")


@router.message(Command("reinit"), IsAdminFilter())
async def cmd_reinit(message: Message):
    await delete_message(message)
    chat_info = await ChatRepo.get_chat(message.chat.id)

    if not chat_info:
        await temp_msg(
            message,
            f"ℹ️ <b>Чат еще не инициализирован</b>\n\n"
            f"Используйте /init для инициализации",
            parse_mode="HTML",
        )
        return

    match = re.search(r"^/reinit(?:@\w+)?\s+(.+)", message.text)
    if not match:
        await temp_msg(
            message,
            "❌ Требуется ввести название КА.\n"
            "Пример: <code>/reinit ABC13 LTD</code>",
            parse_mode="HTML",
        )
        return

    contractor_name = match.group(1).strip()

    balance = await BalanceRepo.get_by_name(contractor_name)
    if not balance:
        balance = await BalanceRepo.create(contractor_name)

    success = await ChatRepo.update_balance(
        chat_id=message.chat.id,
        balance_id=balance['id']
    )

    if success:
        await temp_msg(
            message,
            f"✅ <b>Чат реинициализирован!</b>\n\n"
            f"📝 Контрагент: <b>{contractor_name}</b>\n"
            f"🆔 Баланс ID: <code>{balance['id']}</code>\n"
            f"💵 RUB: <code>{balance['balance_rub']:.2f}</code>\n"
            f"💰 USDT: <code>{balance['balance_usdt']:.8f}</code>",
            parse_mode="HTML",
        )
    else:
        await temp_msg(message, "❌ Ошибка при инициализации чата")


@router.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    if not message.reply_to_message:
        await temp_msg(
            message, "⚠️ Ответьте на сообщение пользователя командой /setadmin"
        )
        return

    target_user = message.reply_to_message.from_user

    if target_user.is_bot:
        await temp_msg(message, "❌ Нельзя назначить бота админом")
        return

    await UserRepo.set_admin(target_user.id, is_admin=True)

    await temp_msg(
        message,
        f"✅ Пользователь назначен администратором:\n"
        f"👤 ID: <code>{target_user.id}</code>\n"
        f"📝 Username: @{target_user.username or 'Не указан'}\n"
        f"📛 Имя: {target_user.first_name}",
        parse_mode="HTML",
    )


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    if not message.reply_to_message:
        await temp_msg(
            message, "⚠️ Ответьте на сообщение пользователя командой /removeadmin"
        )
        return

    target_user = message.reply_to_message.from_user

    if target_user.id in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "Невозможно лишить прав суперадмина")
        return

    await UserRepo.set_admin(target_user.id, is_admin=False)

    await temp_msg(
        message,
        f"✅ Права администратора сняты:\n"
        f"👤 ID: <code>{target_user.id}</code>\n"
        f"📝 Username: @{target_user.username or 'Не указан'}",
        parse_mode="HTML",
    )


@router.message(Command("newsletter"))
async def cmd_newsletter(message: Message, state: FSMContext):
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return
    await delete_message(message)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="cancel_newsletter")

    await state.set_state(NewsletterStates.waiting_for_text)

    bot_message = await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте текст для рассылки по всем чатам.\n"
        "Можете использовать HTML форматирование:\n"
        "• <code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "• <code>&lt;code&gt;код&lt;/code&gt;</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(newsletter_prompt_msg_id=bot_message.message_id)


@router.callback_query(F.data == "cancel_newsletter")
async def cancel_newsletter(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Рассылка отменена")
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.message(NewsletterStates.waiting_for_text)
async def process_newsletter_text(message: Message, state: FSMContext):
    newsletter_text = message.text or message.caption
    await delete_message(message)

    if not newsletter_text:
        await temp_msg(message, "❌ Текст не может быть пустым")
        return

    data = await state.get_data()
    prompt_msg_id = data.get("newsletter_prompt_msg_id")
    if prompt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_msg_id)
        except Exception:
            pass

    all_chats = await ChatRepo.get_all_active_chats()

    if not all_chats:
        await message.answer("⚠️ Нет активных чатов для рассылки")
        await state.clear()
        return

    progress_msg = await message.answer(
        f"📤 Начинаю рассылку...\n"
        f"Всего чатов: {len(all_chats)}"
    )

    success_count = 0
    failed_count = 0
    failed_chats = []

    for chat in all_chats:
        try:
            await message.bot.send_message(
                chat_id=chat['chat_id'],
                text=newsletter_text,
                parse_mode="HTML"
            )
            success_count += 1
        except Exception as e:
            failed_count += 1
            failed_chats.append({
                'chat_id': chat['chat_id'],
                'contractor': chat.get('contractor_name', 'Неизвестно'),
                'error': str(e)
            })

    try:
        await progress_msg.delete()
    except Exception:
        pass

    report = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"• Успешно: {success_count}\n"
        f"• Ошибки: {failed_count}\n"
        f"• Всего чатов: {len(all_chats)}"
    )

    if failed_chats:
        report += "\n\n❌ <b>Не удалось отправить:</b>\n"
        for chat in failed_chats[:5]:
            report += f"• {chat['contractor']} (ID: {chat['chat_id']})\n"

        if len(failed_chats) > 5:
            report += f"... и ещё {len(failed_chats) - 5}"

    await message.answer(report, parse_mode="HTML", reply_markup=get_delete_keyboard())
    await state.clear()
