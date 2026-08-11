from aiogram.filters import Filter
from aiogram.types import Message
from utils.permissions import has_admin_access


class IsAdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return await has_admin_access(message.from_user.id)
