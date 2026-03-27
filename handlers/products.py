from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import async_session
from services.product_service import get_products_with_stock, get_product_by_id, get_stock_count, purchase_product
from utils.keyboards import product_list_keyboard, confirm_purchase_keyboard, back_main_keyboard
from utils.locale import t, get_user_lang
from utils.formatters import format_price


async def products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show product list."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    async with async_session() as session:
        lang = await get_user_lang(session, user_id)
        products = await get_products_with_stock(session)

    if not products:
        await query.edit_message_text(
            t("product_empty", lang),
            reply_markup=back_main_keyboard(lang),
        )
        return

    await query.edit_message_text(
        t("product_list_title", lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=product_list_keyboard(products, lang),
    )


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show product detail and confirm purchase button."""
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[1])
    user_id = update.effective_user.id

    async with async_session() as session:
        lang = await get_user_lang(session, user_id)
        product = await get_product_by_id(session, product_id)
        if not product:
            await query.edit_message_text(
                t("product_not_found", lang),
                reply_markup=back_main_keyboard(lang),
            )
            return
        stock = await get_stock_count(session, product_id)

    warranty = t("product_warranty_none", lang) if product.warranty_hours == 0 else t("product_warranty_hours", lang, hours=product.warranty_hours)

    text = "\n".join([
        f"{product.emoji} **{product.name}**",
        "",
        t("product_price", lang, price=format_price(product.price)),
        f"📦 {t('product_stock', lang, count=stock)}",
        t("product_warranty", lang, warranty=warranty),
    ])
    if product.description:
        text += f"\n\n📝 {product.description}"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=confirm_purchase_keyboard(product_id, lang),
    )


async def confirm_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute purchase."""
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[2])
    user_id = update.effective_user.id

    async with async_session() as session:
        lang = await get_user_lang(session, user_id)
        result = await purchase_product(session, user_id, product_id)

    if result["success"]:
        text = "\n".join([
            t("purchase_success_title", lang),
            "",
            t("purchase_product", lang, name=result["product_name"]),
            t("purchase_price", lang, price=format_price(result["price"])),
            f"🛡️ {result['warranty']}",
            t("purchase_order_id", lang, id=result["order_id"]),
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            t("purchase_account_info", lang),
            f"`{result['data']}`",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            t("purchase_balance_left", lang, balance=format_price(result["balance"])),
        ])
    else:
        text = f"❌ {result['message']}"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(lang),
    )
