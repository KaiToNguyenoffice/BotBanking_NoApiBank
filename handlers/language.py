from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import async_session
from services.wallet_service import get_or_create_user
from utils.keyboards import language_keyboard, back_main_keyboard
from utils.locale import t, get_user_lang


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        t("lang_select"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=language_keyboard(),
    )


async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]  # lang_vi or lang_en
    user_id = update.effective_user.id
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(session, user_id, tg_user.username, tg_user.first_name)
        user.language = lang
        await session.commit()

    lang_name = "Tiếng Việt 🇻🇳" if lang == "vi" else "English 🇺🇸"
    await query.edit_message_text(
        t("lang_changed", lang, lang_name=lang_name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(lang),
    )
