from urllib.parse import quote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import async_session
from services.wallet_service import (
    get_user, create_pending_deposit, get_transaction_history
)
from utils.keyboards import wallet_keyboard, back_main_keyboard
from utils.locale import t, get_user_lang
from utils.formatters import format_price
from config import (
    BANK_ACCOUNT_NUMBER, BANK_ACCOUNT_NAME, BANK_NAME,
    BANK_BIN, MIN_DEPOSIT, VIETQR_TEMPLATE,
)


def _build_vietqr_url(amount: int, content: str) -> str:
    account = BANK_ACCOUNT_NUMBER
    name = quote(BANK_ACCOUNT_NAME)
    info = quote(content)
    return (
        f"https://img.vietqr.io/image/"
        f"{BANK_BIN}-{account}-{VIETQR_TEMPLATE}.png"
        f"?amount={amount}&addInfo={info}&accountName={name}"
    )


async def wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    async with async_session() as session:
        lang = await get_user_lang(session, user_id)
        user = await get_user(session, user_id)
        balance = user.balance if user else 0

    text = "\n".join([
        t("wallet_title", lang),
        "",
        t("wallet_balance", lang, balance=format_price(balance)),
        "",
        t("wallet_choose", lang),
    ])
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=wallet_keyboard(lang),
    )


async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    async with async_session() as session:
        lang = await get_user_lang(session, user_id)

    context.user_data["awaiting_deposit_amount"] = True

    text = "\n".join([
        t("deposit_title", lang),
        t("deposit_prompt", lang),
        "",
        t("deposit_min", lang, min=format_price(MIN_DEPOSIT)),
        t("deposit_example", lang),
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_deposit_amount"):
        return

    user_id = update.effective_user.id
    async with async_session() as session:
        lang = await get_user_lang(session, user_id)

    text = update.message.text.strip().replace(",", "").replace(".", "")
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text(t("deposit_invalid", lang))
        return

    if amount < MIN_DEPOSIT:
        await update.message.reply_text(t("deposit_too_low", lang, min=format_price(MIN_DEPOSIT)))
        return

    context.user_data["awaiting_deposit_amount"] = False

    async with async_session() as session:
        result = await create_pending_deposit(session, user_id, amount, "bank")

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}")
        return

    ref = result["ref"]
    tx_id = result["tx_id"]

    if not BANK_BIN or not BANK_ACCOUNT_NUMBER:
        text = "\n".join([
            t("deposit_title", lang),
            t("deposit_qr_amount", lang, amount=format_price(amount)),
            t("deposit_qr_ref", lang, ref=ref),
            "",
            t("deposit_bank_not_configured", lang),
        ])
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_cancel_order", lang), callback_data=f"cancel_deposit_{tx_id}")],
            ]),
        )
        return

    qr_url = _build_vietqr_url(amount, ref)
    caption = "\n".join([
        t("deposit_title", lang),
        t("deposit_qr_amount", lang, amount=format_price(amount)),
        t("deposit_qr_ref", lang, ref=ref),
        "",
        t("deposit_qr_warning", lang),
    ])
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_cancel_order", lang), callback_data=f"cancel_deposit_{tx_id}")],
    ])

    await update.message.reply_photo(
        photo=qr_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cancel_keyboard,
    )


async def cancel_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = int(query.data.split("_")[2])

    from services.wallet_service import reject_deposit, get_or_create_user
    from utils.keyboards import main_menu_keyboard
    from utils.formatters import format_price

    tg_user = update.effective_user
    async with async_session() as session:
        lang = await get_user_lang(session, tg_user.id)
        result = await reject_deposit(session, tx_id)
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)

    if result["success"]:
        # Delete QR message
        try:
            await query.message.delete()
        except Exception:
            pass

        # Send main menu
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
        await query.message.chat.send_message(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(lang),
        )
    else:
        await query.answer(result["message"], show_alert=True)


async def tx_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    async with async_session() as session:
        lang = await get_user_lang(session, user_id)
        txs = await get_transaction_history(session, user_id, limit=15)

    if not txs:
        text = t("tx_history_empty", lang)
    else:
        lines = [t("tx_history_title", lang), ""]
        for tx in txs:
            icon = "🟢" if tx.type == "deposit" else "🔴" if tx.type == "purchase" else "🔵"
            sign = "+" if tx.amount > 0 else ""
            time_str = tx.created_at.strftime("%d/%m %H:%M") if tx.created_at else ""
            status_icon = "✅" if tx.status == "completed" else "⏳" if tx.status == "pending" else "❌"
            lines.append(f"{icon} {sign}{format_price(tx.amount)} | {status_icon} | {time_str}")
            if tx.note:
                lines.append(f"   ↳ {tx.note}")
        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(lang),
    )
