from config import CURRENCY_SYMBOL


def format_price(amount: float) -> str:
    return f"{amount:,.0f}{CURRENCY_SYMBOL}"


def format_balance(balance: float) -> str:
    return f"💰 Số dư: {format_price(balance)}"


def format_product_detail(product, stock_count: int) -> str:
    warranty = "Không bảo hành" if product.warranty_hours == 0 else f"BH {product.warranty_hours}h"
    lines = [
        f"{product.emoji} **{product.name}**",
        f"",
        f"💵 Giá: {format_price(product.price)}",
        f"📦 Tồn kho: {stock_count}",
        f"🛡️ Bảo hành: {warranty}",
    ]
    if product.description:
        lines.append(f"\n📝 {product.description}")
    return "\n".join(lines)


def format_order_success(result: dict) -> str:
    lines = [
        "✅ **MUA HÀNG THÀNH CÔNG!**",
        "",
        f"📦 Sản phẩm: {result['product_name']}",
        f"💵 Giá: {format_price(result['price'])}",
        f"🛡️ {result['warranty']}",
        f"🆔 Đơn hàng: #{result['order_id']}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📋 **Thông tin tài khoản:**",
        f"`{result['data']}`",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 Số dư còn lại: {format_price(result['balance'])}",
    ]
    return "\n".join(lines)


def format_deposit_info(ref: str, amount: float, bank_name: str, account_number: str, account_name: str) -> str:
    lines = [
        "🏦 **THÔNG TIN CHUYỂN KHOẢN**",
        "",
        f"💵 Số tiền: **{format_price(amount)}**",
        f"🏦 Ngân hàng: **{bank_name}**",
        f"📱 STK: `{account_number}`",
        f"👤 Tên: **{account_name}**",
        f"📝 Nội dung CK: `{ref}`",
        "",
        "⚠️ **LƯU Ý:**",
        "• Chuyển đúng số tiền và nội dung",
        "• Tiền sẽ được cộng sau khi admin xác nhận",
        "• Nếu cần hỗ trợ, liên hệ admin",
    ]
    return "\n".join(lines)


def format_tx_history(transactions: list) -> str:
    if not transactions:
        return "📜 Chưa có giao dịch nào."

    lines = ["📜 **LỊCH SỬ GIAO DỊCH**", ""]
    for tx in transactions:
        icon = "🟢" if tx.type == "deposit" else "🔴" if tx.type == "purchase" else "🔵"
        sign = "+" if tx.amount > 0 else ""
        time_str = tx.created_at.strftime("%d/%m %H:%M") if tx.created_at else ""
        status_icon = "✅" if tx.status == "completed" else "⏳" if tx.status == "pending" else "❌"
        lines.append(
            f"{icon} {sign}{format_price(tx.amount)} | {status_icon} | {time_str}"
        )
        if tx.note:
            lines.append(f"   ↳ {tx.note}")
    return "\n".join(lines)


def format_welcome(user_name: str, balance: float, points: int) -> str:
    lines = [
        f"🛒 **SHOP TỰ ĐỘNG**",
        "",
        f"👋 Xin chào, **{user_name}**!",
        "",
        f"💰 Số dư: **{format_price(balance)}**",
        f"⭐ Điểm: **{points}**",
        "",
        "🤖 Bot hoạt động 24/7 – tự động giao hàng",
        "🎁 Khuyến mãi: Mua 10 tặng 2 (sản phẩm CapCut)",
        "",
        "👇 Chọn sản phẩm để xem chi tiết",
    ]
    return "\n".join(lines)


def format_admin_stats(total_users: int, total_revenue: float, products_data: list) -> str:
    lines = [
        "📊 **THỐNG KÊ HỆ THỐNG**",
        "",
        f"👥 Tổng user: **{total_users}**",
        f"💰 Tổng doanh thu: **{format_price(total_revenue)}**",
        "",
        "📦 **Kho hàng:**",
    ]
    for item in products_data:
        p = item["product"]
        stock = item["stock"]
        lines.append(f"  • {p.name}: **{stock}** còn lại")
    return "\n".join(lines)
