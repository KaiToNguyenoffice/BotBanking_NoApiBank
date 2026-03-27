import random
import string
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Transaction


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str = None,
    first_name: str = None,
) -> User:
    """Get existing user or create new one."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.username = username
        user.first_name = first_name
        user.last_active = datetime.utcnow()
        await session.commit()
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        balance=0.0,
        loyalty_points=0,
        language="vi",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_balance(session: AsyncSession, telegram_id: int) -> float:
    user = await get_user(session, telegram_id)
    return user.balance if user else 0.0


async def deposit(
    session: AsyncSession,
    telegram_id: int,
    amount: float,
    payment_method: str = "admin",
    payment_ref: str = None,
    note: str = None,
) -> dict:
    """Add balance to user account."""
    user_result = await session.execute(
        select(User).where(User.telegram_id == telegram_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "Người dùng không tồn tại."}

    balance_before = user.balance
    user.balance += amount
    balance_after = user.balance

    tx = Transaction(
        user_id=telegram_id,
        type="deposit",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        payment_method=payment_method,
        payment_ref=payment_ref or _gen_ref(),
        status="completed",
        note=note or f"Nạp {amount:,.0f}đ qua {payment_method}",
    )
    session.add(tx)
    await session.commit()

    return {
        "success": True,
        "message": f"Nạp thành công {amount:,.0f}đ",
        "balance": balance_after,
    }


async def create_pending_deposit(
    session: AsyncSession,
    telegram_id: int,
    amount: float,
    payment_method: str = "bank",
) -> dict:
    """Create a pending deposit transaction. Returns payment ref for user to include in transfer."""
    user = await get_user(session, telegram_id)
    if not user:
        return {"success": False, "message": "Người dùng không tồn tại."}

    ref = _gen_ref()
    tx = Transaction(
        user_id=telegram_id,
        type="deposit",
        amount=amount,
        balance_before=user.balance,
        balance_after=user.balance,  # Not yet credited
        payment_method=payment_method,
        payment_ref=ref,
        status="pending",
        note=f"Chờ xác nhận nạp {amount:,.0f}đ",
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)

    return {
        "success": True,
        "ref": ref,
        "tx_id": tx.id,
        "amount": amount,
    }


async def confirm_deposit(session: AsyncSession, tx_id: int) -> dict:
    """Admin: confirm a pending deposit."""
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.status == "pending",
            Transaction.type == "deposit",
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {"success": False, "message": "Giao dịch không tồn tại hoặc đã xử lý."}

    user_result = await session.execute(
        select(User).where(User.telegram_id == tx.user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "Người dùng không tồn tại."}

    tx.balance_before = user.balance
    user.balance += tx.amount
    tx.balance_after = user.balance
    tx.status = "completed"
    tx.note = f"Đã xác nhận nạp {tx.amount:,.0f}đ"

    await session.commit()

    return {
        "success": True,
        "message": f"Đã nạp {tx.amount:,.0f}đ cho user {user.telegram_id}",
        "user_id": user.telegram_id,
        "balance": user.balance,
    }


async def reject_deposit(session: AsyncSession, tx_id: int) -> dict:
    """Reject/cancel a pending deposit — delete from DB."""
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.status == "pending",
            Transaction.type == "deposit",
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {"success": False, "message": "Giao dịch không tồn tại hoặc đã xử lý."}

    await session.delete(tx)
    await session.commit()

    return {"success": True, "message": f"Đã huỷ và xóa giao dịch #{tx_id}"}


async def get_pending_deposits(session: AsyncSession) -> list[Transaction]:
    """Admin: get all pending deposits."""
    result = await session.execute(
        select(Transaction).where(
            Transaction.type == "deposit",
            Transaction.status == "pending",
        ).order_by(Transaction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_transaction_history(
    session: AsyncSession,
    telegram_id: int,
    limit: int = 10,
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(
            Transaction.user_id == telegram_id
        ).order_by(Transaction.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_total_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar() or 0


async def get_total_revenue(session: AsyncSession) -> float:
    result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.type == "purchase",
            Transaction.status == "completed",
        )
    )
    val = result.scalar()
    return abs(val) if val else 0.0


def _gen_ref(length: int = 8) -> str:
    return "NAP" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
