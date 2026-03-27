from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from telegram.constants import ParseMode

from database.db import async_session
from services.product_service import (
    get_products_with_stock, get_all_products, add_product, add_stock_bulk, toggle_product
)
from services.wallet_service import (
    get_pending_deposits, confirm_deposit, reject_deposit,
    get_total_users, get_total_revenue, deposit
)
from utils.keyboards import (
    admin_keyboard, admin_pending_list_keyboard, admin_tx_action_keyboard,
    admin_product_list_keyboard, back_main_keyboard
)
from utils.formatters import format_admin_stats, format_price
from utils.decorators import admin_only
from config import ADMIN_IDS

# Conversation states for admin flows
ADMIN_ADD_NAME, ADMIN_ADD_PRICE, ADMIN_ADD_CATEGORY, ADMIN_ADD_WARRANTY = range(4)
ADMIN_STOCK_SELECT, ADMIN_STOCK_DATA = range(4, 6)
ADMIN_DEPOSIT_USER, ADMIN_DEPOSIT_AMOUNT = range(6, 8)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Bạn không có quyền truy cập.")
        return

    await update.message.reply_text(
        "🔧 **ADMIN PANEL**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_keyboard(),
    )


@admin_only
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔧 **ADMIN PANEL**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_keyboard(),
    )


@admin_only
async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system statistics."""
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        total_users = await get_total_users(session)
        total_revenue = await get_total_revenue(session)
        products_data = await get_products_with_stock(session)

    text = format_admin_stats(total_users, total_revenue, products_data)
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_keyboard(),
    )


# === Add Product Flow ===
@admin_only
async def admin_add_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add product flow."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📦 **THÊM SẢN PHẨM MỚI**\n\nNhập tên sản phẩm:",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["admin_flow"] = "add_product"
    context.user_data["admin_step"] = "name"


# === Import Stock Flow ===
@admin_only
async def admin_import_stock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start import stock flow — show product list."""
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        products = await get_all_products(session)

    await query.edit_message_text(
        "📥 **IMPORT STOCK**\n\nChọn sản phẩm để import:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_product_list_keyboard(products),
    )


@admin_only
async def admin_product_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin selected a product for import/management."""
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[2])
    context.user_data["admin_flow"] = "import_stock"
    context.user_data["admin_product_id"] = product_id

    from services.product_service import get_product_by_id, get_stock_count
    async with async_session() as session:
        product = await get_product_by_id(session, product_id)
        stock = await get_stock_count(session, product_id)

    await query.edit_message_text(
        f"📦 **{product.name}**\n"
        f"📊 Stock hiện tại: {stock}\n\n"
        f"Gửi danh sách tài khoản (mỗi dòng 1 tài khoản):\n\n"
        f"Ví dụ:\n`email1@gmail.com:pass1`\n`email2@gmail.com:pass2`",
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["admin_step"] = "stock_data"


# === Pending Deposits ===
@admin_only
async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending deposit list."""
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        pending = await get_pending_deposits(session)

    if not pending:
        await query.edit_message_text(
            "💳 Không có giao dịch nào đang chờ duyệt.",
            reply_markup=admin_keyboard(),
        )
        return

    await query.edit_message_text(
        f"💳 **DUYỆT NẠP TIỀN** ({len(pending)} đang chờ)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_pending_list_keyboard(pending),
    )


@admin_only
async def admin_tx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detail of a pending transaction."""
    query = update.callback_query
    await query.answer()

    tx_id = int(query.data.split("_")[2])

    from services.wallet_service import get_user
    from database.models import Transaction
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.id == tx_id)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            await query.edit_message_text("❌ Giao dịch không tồn tại.")
            return
        user = await get_user(session, tx.user_id)

    await query.edit_message_text(
        f"💳 **CHI TIẾT GIAO DỊCH #{tx.id}**\n\n"
        f"👤 User: {user.first_name or user.username} ({tx.user_id})\n"
        f"💵 Số tiền: {format_price(tx.amount)}\n"
        f"📝 Mã ref: `{tx.payment_ref}`\n"
        f"📅 Thời gian: {tx.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        f"📊 Trạng thái: ⏳ Đang chờ",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_tx_action_keyboard(tx_id),
    )


@admin_only
async def admin_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve a pending deposit."""
    query = update.callback_query
    await query.answer()

    tx_id = int(query.data.split("_")[2])

    async with async_session() as session:
        result = await confirm_deposit(session, tx_id)

    if result["success"]:
        text = f"✅ {result['message']}\n💰 Số dư mới: {format_price(result['balance'])}"
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=result["user_id"],
                text=f"✅ Nạp tiền thành công!\n💰 Số dư: {format_price(result['balance'])}",
            )
        except Exception:
            pass
    else:
        text = f"❌ {result['message']}"

    await query.edit_message_text(text, reply_markup=admin_keyboard())


@admin_only
async def admin_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject a pending deposit."""
    query = update.callback_query
    await query.answer()

    tx_id = int(query.data.split("_")[2])

    async with async_session() as session:
        result = await reject_deposit(session, tx_id)

    text = f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}"
    await query.edit_message_text(text, reply_markup=admin_keyboard())


# === Admin Text Handler (for multi-step flows) ===
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for admin flows (add product, import stock, manual deposit)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    flow = context.user_data.get("admin_flow")
    step = context.user_data.get("admin_step")

    if not flow or not step:
        return

    text = update.message.text.strip()

    # === Add Product Flow ===
    if flow == "add_product":
        if step == "name":
            context.user_data["new_product_name"] = text
            context.user_data["admin_step"] = "price"
            await update.message.reply_text("💵 Nhập giá (VNĐ):")
            return

        if step == "price":
            try:
                price = float(text.replace(",", "").replace(".", ""))
            except ValueError:
                await update.message.reply_text("❌ Giá không hợp lệ. Nhập lại:")
                return
            context.user_data["new_product_price"] = price
            context.user_data["admin_step"] = "category"
            await update.message.reply_text(
                "📁 Nhập category (hoặc gõ `skip` để bỏ qua):",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if step == "category":
            category = "" if text.lower() == "skip" else text
            context.user_data["new_product_category"] = category
            context.user_data["admin_step"] = "warranty"
            await update.message.reply_text(
                "🛡️ Số giờ bảo hành (0 = KBH, 24 = BH 24h):"
            )
            return

        if step == "warranty":
            try:
                warranty = int(text)
            except ValueError:
                await update.message.reply_text("❌ Nhập số nguyên:")
                return

            async with async_session() as session:
                product = await add_product(
                    session,
                    name=context.user_data["new_product_name"],
                    price=context.user_data["new_product_price"],
                    category=context.user_data.get("new_product_category", ""),
                    warranty_hours=warranty,
                )

            context.user_data.pop("admin_flow", None)
            context.user_data.pop("admin_step", None)

            await update.message.reply_text(
                f"✅ Đã thêm sản phẩm:\n"
                f"📦 {product.name}\n"
                f"💵 {format_price(product.price)}\n"
                f"🛡️ BH: {warranty}h\n"
                f"🆔 ID: {product.id}",
                reply_markup=admin_keyboard(),
            )
            return

    # === Import Stock Flow ===
    if flow == "import_stock" and step == "stock_data":
        product_id = context.user_data.get("admin_product_id")
        items = text.split("\n")

        async with async_session() as session:
            count = await add_stock_bulk(session, product_id, items)

        context.user_data.pop("admin_flow", None)
        context.user_data.pop("admin_step", None)

        await update.message.reply_text(
            f"✅ Đã import **{count}** tài khoản vào kho.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_keyboard(),
        )
        return

    # === Manual Deposit Flow ===
    if flow == "manual_deposit":
        if step == "user_id":
            try:
                target_user_id = int(text)
            except ValueError:
                await update.message.reply_text("❌ User ID không hợp lệ.")
                return
            context.user_data["deposit_target_user"] = target_user_id
            context.user_data["admin_step"] = "amount"
            await update.message.reply_text("💵 Nhập số tiền nạp (VNĐ):")
            return

        if step == "amount":
            try:
                amount = float(text.replace(",", "").replace(".", ""))
            except ValueError:
                await update.message.reply_text("❌ Số tiền không hợp lệ.")
                return

            target_user_id = context.user_data["deposit_target_user"]
            async with async_session() as session:
                result = await deposit(
                    session, target_user_id, amount,
                    payment_method="admin",
                    note=f"Admin nạp {format_price(amount)}",
                )

            context.user_data.pop("admin_flow", None)
            context.user_data.pop("admin_step", None)

            if result["success"]:
                await update.message.reply_text(
                    f"✅ {result['message']}\n💰 Số dư: {format_price(result['balance'])}",
                    reply_markup=admin_keyboard(),
                )
                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"✅ Admin đã nạp {format_price(amount)} vào ví của bạn!\n"
                             f"💰 Số dư: {format_price(result['balance'])}",
                    )
                except Exception:
                    pass
            else:
                await update.message.reply_text(
                    f"❌ {result['message']}",
                    reply_markup=admin_keyboard(),
                )
            return

    # === Lookup User Flow ===
    if flow == "lookup_user" and step == "user_id":
        try:
            target_user_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ User ID không hợp lệ.")
            return

        context.user_data.pop("admin_flow", None)
        context.user_data.pop("admin_step", None)

        from services.wallet_service import get_user
        from database.models import Order, Transaction
        from sqlalchemy import select, func

        async with async_session() as session:
            user = await get_user(session, target_user_id)
            if not user:
                await update.message.reply_text(
                    f"❌ Không tìm thấy user có ID: `{target_user_id}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=admin_keyboard(),
                )
                return

            # Tổng đơn hàng
            order_count_result = await session.execute(
                select(func.count()).select_from(Order).where(Order.user_id == target_user_id)
            )
            total_orders = order_count_result.scalar() or 0

            # Tổng chi tiêu
            spent_result = await session.execute(
                select(func.sum(Order.price_paid)).where(Order.user_id == target_user_id)
            )
            total_spent = spent_result.scalar() or 0

            # Tổng nạp
            deposited_result = await session.execute(
                select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == target_user_id,
                    Transaction.type == "deposit",
                    Transaction.status == "completed",
                )
            )
            total_deposited = deposited_result.scalar() or 0

            # 5 đơn hàng gần nhất
            recent_orders_result = await session.execute(
                select(Order).where(Order.user_id == target_user_id)
                .order_by(Order.created_at.desc()).limit(5)
            )
            recent_orders = list(recent_orders_result.scalars().all())

        joined = user.created_at.strftime("%d/%m/%Y %H:%M") if user.created_at else "N/A"
        last_active_str = user.last_active.strftime("%d/%m/%Y %H:%M") if user.last_active else "N/A"

        lines = [
            f"🔍 **THÔNG TIN KHÁCH HÀNG**",
            "",
            f"🆔 ID: `{user.telegram_id}`",
            f"👤 Username: @{user.username}" if user.username else "👤 Username: Không có",
            f"📛 Tên: {user.first_name or 'N/A'}",
            f"🌐 Ngôn ngữ: {'🇻🇳 VI' if user.language == 'vi' else '🇺🇸 EN'}",
            "",
            f"💰 Số dư: **{format_price(user.balance)}**",
            f"⭐ Điểm: **{user.loyalty_points}**",
            f"💳 Tổng nạp: {format_price(total_deposited)}",
            f"🛒 Tổng đơn: {total_orders}",
            f"💸 Tổng chi tiêu: {format_price(total_spent)}",
            "",
            f"📅 Tham gia: {joined}",
            f"🕐 Hoạt động: {last_active_str}",
        ]

        if recent_orders:
            lines.append("")
            lines.append("📦 **5 đơn gần nhất:**")
            for o in recent_orders:
                time_str = o.created_at.strftime("%d/%m %H:%M") if o.created_at else ""
                lines.append(f"  • #{o.id} | {format_price(o.price_paid)} | {time_str}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_keyboard(),
        )
        return
@admin_only
async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual deposit — ask for user ID."""
    query = update.callback_query
    await query.answer()

    context.user_data["admin_flow"] = "manual_deposit"
    context.user_data["admin_step"] = "user_id"

    await query.edit_message_text(
        "👥 **NẠP TIỀN THỦ CÔNG**\n\nNhập Telegram User ID:",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def admin_lookup_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lookup user — ask for user ID."""
    query = update.callback_query
    await query.answer()

    context.user_data["admin_flow"] = "lookup_user"
    context.user_data["admin_step"] = "user_id"

    await query.edit_message_text(
        "🔍 **TRA CỨU KHÁCH HÀNG**\n\nNhập Telegram User ID:",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def admin_list_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered users with their IDs."""
    query = update.callback_query
    await query.answer()

    from database.models import User
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = list(result.scalars().all())

    if not users:
        await query.edit_message_text(
            "👥 Chưa có khách hàng nào.",
            reply_markup=admin_keyboard(),
        )
        return

    lines = [f"👥 **DANH SÁCH KHÁCH HÀNG** ({len(users)} người)", ""]
    for u in users:
        name = u.first_name or u.username or "N/A"
        username = f"@{u.username}" if u.username else ""
        lines.append(
            f"• `{u.telegram_id}` | {name} {username} | {format_price(u.balance)}"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_keyboard(),
    )
