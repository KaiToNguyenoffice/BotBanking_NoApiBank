from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import async_session
from services.wallet_service import get_or_create_user
from utils.keyboards import main_menu_keyboard
from utils.locale import t, get_user_lang
from utils.formatters import format_price


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    tg_user = update.effective_user
    async with async_session() as session:
        user = await get_or_create_user(
            session, tg_user.id, tg_user.username, tg_user.first_name
        )
        lang = user.language or "vi"

    name = user.first_name or user.username or "bạn"
    text = "\n".join([
        t("welcome_title", lang),
        "",
        t("welcome_greeting", lang, name=name),
        "",
        t("welcome_balance", lang, balance=format_price(user.balance)),
        t("welcome_points", lang, points=user.loyalty_points),
        "",
        t("welcome_info", lang),
        "",
        t("welcome_cta", lang),
    ])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(lang),
    )


async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to main menu callback."""
    query = update.callback_query
    await query.answer()

    tg_user = update.effective_user
    async with async_session() as session:
        user = await get_or_create_user(
            session, tg_user.id, tg_user.username, tg_user.first_name
        )
        lang = user.language or "vi"

    name = user.first_name or user.username or "bạn"
    text = "\n".join([
        t("welcome_title", lang),
        "",
        t("welcome_greeting", lang, name=name),
        "",
        t("welcome_balance", lang, balance=format_price(user.balance)),
        t("welcome_points", lang, points=user.loyalty_points),
        "",
        t("welcome_info", lang),
        "",
        t("welcome_cta", lang),
    ])

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(lang),
    )


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refresh callback — same as back to main."""
    await back_main_callback(update, context)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myid — show user their Telegram ID."""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 **Telegram ID của bạn:**\n`{user.id}`\n\n"
        f"📋 Nhấn vào số trên để copy.",
        parse_mode=ParseMode.MARKDOWN,
    )
