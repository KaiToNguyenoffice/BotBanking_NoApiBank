from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    balance = Column(Float, default=0.0, nullable=False)
    loyalty_points = Column(Integer, default=0, nullable=False)
    language = Column(String(5), default="vi", nullable=False)
    last_daily = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_active = Column(DateTime, default=func.now(), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="user", lazy="selectin")
    orders = relationship("Order", back_populates="user", lazy="selectin")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=True)
    emoji = Column(String(10), default="🔥")
    is_active = Column(Boolean, default=True, nullable=False)
    warranty_hours = Column(Integer, default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    stock_items = relationship("StockItem", back_populates="product", lazy="selectin")
    orders = relationship("Order", back_populates="product", lazy="selectin")


class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    data = Column(Text, nullable=False)
    status = Column(String(20), default="available", nullable=False)  # available | sold | expired
    sold_to = Column(BigInteger, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    product = relationship("Product", back_populates="stock_items")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    type = Column(String(20), nullable=False)  # deposit | purchase | refund
    amount = Column(Float, nullable=False)
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"), nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_ref = Column(String(100), nullable=True)
    status = Column(String(20), default="completed", nullable=False)  # pending | completed | failed
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", back_populates="transactions")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"), nullable=False)
    price_paid = Column(Float, nullable=False)
    status = Column(String(20), default="delivered", nullable=False)  # delivered | refunded
    warranty_until = Column(DateTime, nullable=True)
    delivered_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
