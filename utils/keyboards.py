from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.locale import t


def main_menu_keyboard(lang: str = "vi") -> InlineKeyboardMarkup:
    """Main menu keyboard matching the reference bot layout."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_products", lang), callback_data="products")],
        [
            InlineKeyboardButton(t("btn_daily", lang), callback_data="daily"),
            InlineKeyboardButton(t("btn_redeem", lang), callback_data="redeem_capcut"),
        ],
        [
            InlineKeyboardButton(t("btn_wallet", lang), callback_data="wallet"),
            InlineKeyboardButton(t("btn_deposit", lang), callback_data="deposit"),
        ],
        [
            InlineKeyboardButton(t("btn_refresh", lang), callback_data="refresh"),
            InlineKeyboardButton(t("btn_language", lang), callback_data="language"),
        ],
        [InlineKeyboardButton(t("btn_api_key", lang), callback_data="api_key")],
    ])


def product_list_keyboard(products_with_stock: list[dict], lang: str = "vi") -> InlineKeyboardMarkup:
    buttons = []
    for item in products_with_stock:
        p = item["product"]
        stock = item["stock"]
        stock_text = t("product_stock", lang, count=stock)
        text = f"{p.emoji} {p.name} — {p.price:,.0f}đ ({stock_text})"
        buttons.append([InlineKeyboardButton(text, callback_data=f"buy_{p.id}")])
    buttons.append([InlineKeyboardButton(t("btn_back", lang), callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def confirm_purchase_keyboard(product_id: int, lang: str = "vi") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_confirm", lang), callback_data=f"confirm_buy_{product_id}"),
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="products"),
        ]
    ])


def wallet_keyboard(lang: str = "vi") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_tx_history", lang), callback_data="tx_history")],
        [InlineKeyboardButton(t("btn_deposit", lang), callback_data="deposit")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="back_main")],
    ])


def back_main_keyboard(lang: str = "vi") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_back_main", lang), callback_data="back_main")]
    ])


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Thống kê", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Thêm sản phẩm", callback_data="admin_add_product")],
        [InlineKeyboardButton("📥 Import stock", callback_data="admin_import_stock")],
        [InlineKeyboardButton("💳 Duyệt nạp tiền", callback_data="admin_pending")],
        [InlineKeyboardButton("👥 Nạp tiền thủ công", callback_data="admin_users")],
        [InlineKeyboardButton("🔍 Tra cứu khách hàng", callback_data="admin_lookup_user")],
        [InlineKeyboardButton("📋 Danh sách KH", callback_data="admin_list_users")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main")],
    ])


def admin_pending_list_keyboard(transactions: list) -> InlineKeyboardMarkup:
    buttons = []
    for tx in transactions:
        text = f"#{tx.id} | User {tx.user_id} | {tx.amount:,.0f}đ | {tx.payment_ref}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"admin_tx_{tx.id}")])
    buttons.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_menu")])
    return InlineKeyboardMarkup(buttons)


def admin_tx_action_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"admin_approve_{tx_id}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"admin_reject_{tx_id}"),
        ],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_pending")],
    ])


def admin_product_list_keyboard(products: list) -> InlineKeyboardMarkup:
    buttons = []
    for p in products:
        status = "✅" if p.is_active else "❌"
        buttons.append([InlineKeyboardButton(
            f"{status} {p.name} — {p.price:,.0f}đ",
            callback_data=f"admin_prod_{p.id}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_menu")])
    return InlineKeyboardMarkup(buttons)
