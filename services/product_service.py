from datetime import datetime, timedelta
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product, StockItem, Order, Transaction, User


async def get_all_products(session: AsyncSession) -> list[Product]:
    """Get all active products with stock count."""
    result = await session.execute(
        select(Product).where(Product.is_active == True).order_by(Product.sort_order)
    )
    return list(result.scalars().all())


async def get_product_by_id(session: AsyncSession, product_id: int) -> Product | None:
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def get_stock_count(session: AsyncSession, product_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(StockItem).where(
            StockItem.product_id == product_id,
            StockItem.status == "available"
        )
    )
    return result.scalar() or 0


async def get_products_with_stock(session: AsyncSession) -> list[dict]:
    """Get all active products with their available stock count."""
    products = await get_all_products(session)
    result = []
    for p in products:
        count = await get_stock_count(session, p.id)
        result.append({"product": p, "stock": count})
    return result


async def purchase_product(
    session: AsyncSession,
    user_id: int,
    product_id: int,
) -> dict:
    """
    Atomic purchase: check balance, deduct, grab stock, create order.
    Returns dict with 'success', 'message', 'data'.
    """
    # Get user
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "Người dùng không tồn tại."}

    # Get product
    product = await get_product_by_id(session, product_id)
    if not product or not product.is_active:
        return {"success": False, "message": "Sản phẩm không tồn tại hoặc đã ngừng bán."}

    # Check balance
    if user.balance < product.price:
        deficit = product.price - user.balance
        return {
            "success": False,
            "message": f"Số dư không đủ. Cần nạp thêm {deficit:,.0f}đ."
        }

    # Grab available stock
    stock_result = await session.execute(
        select(StockItem).where(
            StockItem.product_id == product_id,
            StockItem.status == "available"
        ).limit(1).with_for_update()
    )
    stock_item = stock_result.scalar_one_or_none()
    if not stock_item:
        return {"success": False, "message": "Sản phẩm đã hết hàng."}

    # === Execute purchase ===
    balance_before = user.balance
    user.balance -= product.price
    balance_after = user.balance

    # Save data before deleting stock item
    stock_data = stock_item.data
    stock_item_id = stock_item.id

    # Calculate warranty
    warranty_until = None
    if product.warranty_hours > 0:
        warranty_until = datetime.utcnow() + timedelta(hours=product.warranty_hours)

    # Create order (lưu thông tin tài khoản vào order trước khi xóa stock)
    order = Order(
        user_id=user_id,
        product_id=product_id,
        stock_item_id=stock_item_id,
        price_paid=product.price,
        status="delivered",
        warranty_until=warranty_until,
        delivered_data=stock_data,
    )
    session.add(order)

    # Create transaction record
    tx = Transaction(
        user_id=user_id,
        type="purchase",
        amount=-product.price,
        balance_before=balance_before,
        balance_after=balance_after,
        product_id=product_id,
        stock_item_id=stock_item_id,
        status="completed",
        note=f"Mua {product.name}",
    )
    session.add(tx)

    # Xóa stock item đã bán khỏi DB
    await session.delete(stock_item)

    await session.commit()

    warranty_text = "Không bảo hành"
    if product.warranty_hours > 0:
        warranty_text = f"BH {product.warranty_hours}h (đến {warranty_until.strftime('%d/%m %H:%M')})"

    return {
        "success": True,
        "message": "Mua hàng thành công!",
        "data": stock_item.data,
        "product_name": product.name,
        "price": product.price,
        "balance": balance_after,
        "warranty": warranty_text,
        "order_id": order.id,
    }


async def add_product(
    session: AsyncSession,
    name: str,
    price: float,
    category: str = "",
    emoji: str = "🔥",
    warranty_hours: int = 0,
    description: str = "",
    sort_order: int = 0,
) -> Product:
    """Admin: add a new product."""
    product = Product(
        name=name,
        price=price,
        category=category,
        emoji=emoji,
        warranty_hours=warranty_hours,
        description=description,
        sort_order=sort_order,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def toggle_product(session: AsyncSession, product_id: int) -> bool:
    """Toggle product active/inactive. Returns new state."""
    product = await get_product_by_id(session, product_id)
    if not product:
        return False
    product.is_active = not product.is_active
    await session.commit()
    return product.is_active


async def add_stock_bulk(
    session: AsyncSession,
    product_id: int,
    items: list[str],
) -> int:
    """Admin: add multiple stock items. Returns count added."""
    count = 0
    for data in items:
        data = data.strip()
        if not data:
            continue
        item = StockItem(product_id=product_id, data=data, status="available")
        session.add(item)
        count += 1
    await session.commit()
    return count
