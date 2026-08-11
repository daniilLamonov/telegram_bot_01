"""Helpers for resolving user roles from configuration and the database."""

from config import settings
from database.repositories import UserRepo


def is_super_admin(user_id: int) -> bool:
    """Return whether ``user_id`` is configured as a super-administrator."""
    return user_id in settings.SUPER_ADMIN_ID


async def has_admin_access(user_id: int) -> bool:
    """Return whether a user has regular administrative access.

    Super-administrators receive all regular administrator permissions from the
    configuration and do not need a duplicate ``is_admin`` flag in the database.
    """
    return is_super_admin(user_id) or await UserRepo.is_admin(user_id)
