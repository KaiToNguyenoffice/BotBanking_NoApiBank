import asyncio
import logging

from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from config import BOT_TOKEN
from database.db import init_db

# Handlers
from handlers.start import start_command, back_main_callback, refresh_callback, myid_command
from handlers.products import products_callback, buy_callback, confirm_buy_callback
from handlers.wallet import (
    wallet_callback, deposit_callback, cancel_deposit_callback,
    tx_history_callback, handle_custom_amount,
)
from handlers.loyalty import daily_callback, redeem_capcut_callback
from handlers.language import language_callback, set_language_callback
from handlers.admin import (
    admin_command, admin_menu_callback, admin_stats_callback,
    admin_add_product_callback, admin_import_stock_callback,
    admin_product_select_callback, admin_pending_callback,
    admin_tx_callback, admin_approve_callback, admin_reject_callback,
    admin_text_handler, admin_users_callback, admin_lookup_user_callback,
    admin_list_users_callback,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN chưa được cấu hình! Tạo file .env từ .env.example")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # === Commands ===
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("myid", myid_command))

    # === Callback Queries ===
    # Main menu
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh$"))

    # Products
    app.add_handler(CallbackQueryHandler(products_callback, pattern="^products$"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_buy_callback, pattern=r"^confirm_buy_\d+$"))

    # Wallet
    app.add_handler(CallbackQueryHandler(wallet_callback, pattern="^wallet$"))
    app.add_handler(CallbackQueryHandler(deposit_callback, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(cancel_deposit_callback, pattern=r"^cancel_deposit_\d+$"))
    app.add_handler(CallbackQueryHandler(tx_history_callback, pattern="^tx_history$"))

    # Loyalty
    app.add_handler(CallbackQueryHandler(daily_callback, pattern="^daily$"))
    app.add_handler(CallbackQueryHandler(redeem_capcut_callback, pattern="^redeem_capcut$"))

    # Language
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^language$"))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern=r"^lang_(vi|en)$"))

    # API Key (placeholder)
    async def api_key_callback(update, context):
        query = update.callback_query
        await query.answer()
        from utils.locale import t, get_user_lang
        from database.db import async_session as _session
        async with _session() as session:
            lang = await get_user_lang(session, update.effective_user.id)
        await query.edit_message_text(
            t("api_key_placeholder", lang),
            parse_mode="Markdown",
        )
    app.add_handler(CallbackQueryHandler(api_key_callback, pattern="^api_key$"))

    # Admin
    app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_add_product_callback, pattern="^admin_add_product$"))
    app.add_handler(CallbackQueryHandler(admin_import_stock_callback, pattern="^admin_import_stock$"))
    app.add_handler(CallbackQueryHandler(admin_product_select_callback, pattern=r"^admin_prod_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_pending_callback, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_tx_callback, pattern=r"^admin_tx_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_approve_callback, pattern=r"^admin_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_reject_callback, pattern=r"^admin_reject_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_lookup_user_callback, pattern="^admin_lookup_user$"))
    app.add_handler(CallbackQueryHandler(admin_list_users_callback, pattern="^admin_list_users$"))

    # Text handlers — different groups so both can potentially process
    # Group 0: admin flows (returns early if not in admin flow)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler), group=0)
    # Group 1: wallet custom amount input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_amount), group=1)

    # Init DB then start polling
    async def post_init(application):
        await init_db()
        logger.info("Database initialized successfully.")
        
        # Start auto-deposit webhook server
        from services.webhook_service import start_webhook_server
        asyncio.create_task(start_webhook_server(application))

    app.post_init = post_init

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
