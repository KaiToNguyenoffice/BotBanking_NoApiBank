from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import async_session
from services.wallet_service import get_or_create_user
from utils.keyboards import back_main_keyboard
from utils.locale import t, get_user_lang
from utils.formatters import format_price
from config import DAILY_POINTS


async def daily_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(session, user_id, tg_user.username, tg_user.first_name)
        lang = user.language or "vi"

        today = date.today()
        if user.last_daily and user.last_daily.date() == today:
            await query.edit_message_text(
                t("daily_already", lang, points=user.loyalty_points),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_main_keyboard(lang),
            )
            return

        user.loyalty_points += DAILY_POINTS
        user.last_daily = datetime.utcnow()
        await session.commit()

        await query.edit_message_text(
            t("daily_success", lang, earned=DAILY_POINTS, points=user.loyalty_points),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(lang),
        )


async def redeem_capcut_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    REQUIRED_POINTS = 2
    user_id = update.effective_user.id
    tg_user = update.effective_user

    async with async_session() as session:
        user = await get_or_create_user(session, user_id, tg_user.username, tg_user.first_name)
        lang = user.language or "vi"

        if user.loyalty_points < REQUIRED_POINTS:
            deficit = REQUIRED_POINTS - user.loyalty_points
            text = "\n".join([
                t("redeem_title", lang),
                "",
                t("redeem_current", lang, current=user.loyalty_points),
                t("redeem_required", lang, required=REQUIRED_POINTS),
                t("redeem_deficit", lang, deficit=deficit),
                "",
                t("redeem_hint", lang),
            ])
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_main_keyboard(lang),
            )
            return

        from services.product_service import get_stock_count
        from sqlalchemy import select
        from database.models import Product, StockItem, Order

        result = await session.execute(
            select(Product).where(Product.category == "capcut", Product.is_active == True).limit(1)
        )
        capcut_product = result.scalar_one_or_none()

        if not capcut_product:
            await query.edit_message_text(
                t("redeem_no_product", lang),
                reply_markup=back_main_keyboard(lang),
            )
            return

        stock_count = await get_stock_count(session, capcut_product.id)
        if stock_count == 0:
            await query.edit_message_text(
                t("redeem_out_of_stock", lang),
                reply_markup=back_main_keyboard(lang),
            )
            return

        stock_result = await session.execute(
            select(StockItem).where(
                StockItem.product_id == capcut_product.id,
                StockItem.status == "available",
            ).limit(1)
        )
        stock_item = stock_result.scalar_one_or_none()

        # Lưu data trước khi xóa
        stock_data = stock_item.data
        stock_item_id = stock_item.id

        user.loyalty_points -= REQUIRED_POINTS

        order = Order(
            user_id=user_id,
            product_id=capcut_product.id,
            stock_item_id=stock_item_id,
            price_paid=0,
            status="delivered",
            delivered_data=stock_data,
        )
        session.add(order)

        # Xóa stock item đã bán
        await session.delete(stock_item)
        await session.commit()

        text = "\n".join([
            t("redeem_success", lang),
            "",
            f"📦 {capcut_product.name}",
            f"⭐ -{REQUIRED_POINTS}",
            t("redeem_current", lang, current=user.loyalty_points),
            "",
            "━━━━━━━━━━━━━━━━",
            t("purchase_account_info", lang),
            f"`{stock_data}`",
            "━━━━━━━━━━━━━━━━",
        ])
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(lang),
        )
