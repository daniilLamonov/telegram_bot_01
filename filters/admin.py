from aiogram.filters import Filter
from aiogram.types import Message
from database.repositories import UserRepo


class IsAdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return await UserRepo.is_admin(message.from_user.id)
