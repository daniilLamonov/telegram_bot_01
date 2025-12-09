from utils.callbacks import router as callbacks_router

from .admin import router as admin_router
from .balance_up import router as balance_up_router
from .check import router as check_router
from .common import router as common_router
from .exchange import router as exchange_router
from .export import router as export_router
from .help import router as help_router
from .payments import router as payments_router

__all__ = [
    "common_router",
    "help_router",
    "balance_up_router",
    "payments_router",
    "check_router",
    "exchange_router",
    "admin_router",
    "export_router",
    "callbacks_router",
]
