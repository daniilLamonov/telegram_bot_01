from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from filters.admin import IsAdminFilter
from utils.generate_qr import generate_qr
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="qr")


@router.message(Command("qr"), IsAdminFilter())
async def cmd_new(message: Message):
    await delete_message(message)
    args = message.text.split()[1:]

    if not args:
        await temp_msg(message, "Использование: /qr <сумма>")
        return

    try:
        amount = float(args[0].replace(",", "."))

        qr, data = generate_qr(amount)



        if not qr:
            await message.answer(
                "❌ Файл/фото не найден\n",
                parse_mode="HTML",
                reply_markup=get_delete_keyboard(),
            )
        await message.answer_photo(
            photo=FSInputFile(filepath),
            caption=data,
            parse_mode="HTML",
            reply_markup=get_delete_keyboard(),
        )


        # chat_id = message.chat.id
        # balance_id = await ChatRepo.get_balance_id(chat_id)
        # if not balance_id:
        #     await temp_msg(message, "❌ Чат не инициализирован")
        #     return
        #
        # await BalanceRepo.set_commission(balance_id, percent)
        #
        # await temp_msg(message, f"✅ Комиссия баланса: {percent:.2f}%")

    except (ValueError, IndexError):
        await temp_msg(message, "❌ Введите корректный процент")