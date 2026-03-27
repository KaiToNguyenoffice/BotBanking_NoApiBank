import functools
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS


def admin_only(func):
    """Decorator to restrict handler to admin users only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("⛔ Bạn không có quyền truy cập.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
