from utils.callbacks import router as callbacks_router
from .admin import router as admin_router
from .balance_up import router as balance_up_router
from .check import router as check_router
from .common import router as common_router
from .exchange import router as exchange_router
from .export import router as export_router
from .help import router as help_router
from .payments import router as payments_router
from .history import router as history_router
from aiogram import Router

router = Router()

router.include_router(callbacks_router)
router.include_router(check_router)
router.include_router(common_router)
router.include_router(balance_up_router)
router.include_router(payments_router)
router.include_router(exchange_router)
router.include_router(help_router)
router.include_router(export_router)
router.include_router(history_router)
router.include_router(admin_router)
