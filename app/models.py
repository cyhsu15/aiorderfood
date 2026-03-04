from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import Enum as SAEnum
from typing import Any, Dict, List, Optional
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index
from sqlalchemy import (
    Integer,
    BigInteger,
    String,
    Boolean,
    Numeric,
    Text,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


# -------------------------------------------------
# OrderStatus Enum (訂單狀態枚舉)
# -------------------------------------------------
class OrderStatus(str, Enum):
    """訂單狀態枚舉值"""
    PENDING = "pending"          # 待處理
    CONFIRMED = "confirmed"      # 已確認
    PREPARING = "preparing"      # 準備中
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消
    PREORDER = "preorder"        # 預訂


# -------------------------------------------------
# Category (類別資料表)
# -------------------------------------------------
class Category(Base):
    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name_zh: Mapped[str] = mapped_column(Text, nullable=False, comment="中文名稱")
    name_en: Mapped[Optional[str]] = mapped_column(Text, comment="英文名稱")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="顯示排序")

    # 關聯
    dishes: Mapped[List[Dish]] = relationship("Dish", back_populates="category")


# -------------------------------------------------
# Dish (菜色資料表)
# -------------------------------------------------
class Dish(Base):
    __tablename__ = "dish"
    __table_args__ = (
            Index("ix_dish_category_id", "category_id"),
        )
    
    dish_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("category.category_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name_zh: Mapped[str] = mapped_column(Text, nullable=False, comment="中文名稱")
    is_set: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否為套餐")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="顯示排序")

    # 關聯
    category: Mapped[Category] = relationship("Category", back_populates="dishes")
    prices: Mapped[List[DishPrice]] = relationship("DishPrice", back_populates="dish", cascade="all, delete-orphan")
    translations: Mapped[List[DishTranslation]] = relationship("DishTranslation", back_populates="dish", cascade="all, delete-orphan")
    set_items_as_parent: Mapped[List[SetItem]] = relationship("SetItem", foreign_keys="[SetItem.set_id]", cascade="all, delete-orphan")
    set_items_as_child: Mapped[List[SetItem]] = relationship("SetItem", foreign_keys="[SetItem.item_id]")
    detail: Mapped[Optional[DishDetail]] = relationship("DishDetail", back_populates="dish", uselist=False, cascade="all, delete-orphan")


# -------------------------------------------------
# DishPrice (菜色價格)
# -------------------------------------------------
class DishPrice(Base):
    __tablename__ = "dish_price"
    __table_args__ = (
            Index("ix_dish_price_dish_id", "dish_id"),
        )
    price_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dish.dish_id", ondelete="CASCADE"), nullable=False)
    price_label: Mapped[Optional[str]] = mapped_column(Text, comment="價格標籤(小中大)")
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), comment="售價")

    dish: Mapped[Dish] = relationship("Dish", back_populates="prices")


# -------------------------------------------------
# DishTranslation (多語名稱)
# -------------------------------------------------
class DishTranslation(Base):
    __tablename__ = "dish_translation"
    __table_args__ = (
        Index("ix_dish_translation_dish_id", "dish_id"),
        Index("ix_dish_translation_lang", "lang"),
    )
    
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dish.dish_id", ondelete="CASCADE"), primary_key=True)
    lang: Mapped[str] = mapped_column(String(10), primary_key=True, comment="語言代碼")
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="對應語言名稱")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="對應語言描述")

    dish: Mapped[Dish] = relationship("Dish", back_populates="translations")


# -------------------------------------------------
# SetItem (套餐內容)
# -------------------------------------------------
class SetItem(Base):
    __tablename__ = "set_item"
    __table_args__ = (
            Index("ix_set_item_set_id", "set_id"),
            Index("ix_set_item_item_id", "item_id"),
        )
    set_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dish.dish_id", ondelete="CASCADE"),
        primary_key=True,
        comment="套餐ID(父項)",
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("dish.dish_id", ondelete="RESTRICT"),
        primary_key=True,
        comment="子項ID",
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="數量")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="顯示排序")


# -------------------------------------------------
# DishDetail (餐點詳細內容)
# -------------------------------------------------
class DishDetail(Base):
    __tablename__ = "dish_detail"

    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dish.dish_id", ondelete="CASCADE"), primary_key=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, comment="圖片URL")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="詳細描述")
    tags: Mapped[Optional[str]] = mapped_column(Text, comment="餐點標籤 (例如: 素食, 豬肉, 辣)")

    # 關聯
    dish: Mapped[Dish] = relationship("Dish", back_populates="detail")


# -------------------------------------------------
# UserSession (使用者 Session 與購物車資料)
# -------------------------------------------------
class UserSession(Base):
    __tablename__ = "user_session"
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="桌號標籤 (例如: A1, B2)")
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, comment="Session 任意資料 (含購物車)")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="版本號，用於樂觀鎖定")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 關聯
    orders: Mapped[List[Order]] = relationship("Order", back_populates="session")


# -------------------------------------------------
# Order (訂單主檔)
# -------------------------------------------------
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
            Index("ix_orders_session_id", "session_id"),
            Index("ix_orders_status", "status"),
            Index("ix_orders_created_at", "created_at"),
        )
    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_session.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    table_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="桌號標籤 (從 session 複製)")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False, default=OrderStatus.PENDING.value, comment="訂單狀態"
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="訂單總金額")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="訂單備註")
    contact_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="聯絡人姓名")
    contact_phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="聯絡人電話")
    cart_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, comment="下單時購物車快照")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 關聯
    session: Mapped[Optional[UserSession]] = relationship("UserSession", back_populates="orders")
    items: Mapped[List[OrderItem]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# -------------------------------------------------
# OrderItem (訂單明細)
# -------------------------------------------------
class OrderItem(Base):
    __tablename__ = "order_item"
    __table_args__ = (
            Index("ix_order_item_order_id", "order_id"),
        )
    order_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    dish_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("dish.dish_id", ondelete="SET NULL"), nullable=True, comment="菜色ID (可能為空，因歷史資料可能被刪除)")
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="菜色名稱快照")
    size_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="份量/尺寸標籤")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="客製備註")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="數量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="單價")
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="明細小計")
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, comment="額外資訊 (例如: 圖片URL)")

    # 關聯
    order: Mapped[Order] = relationship("Order", back_populates="items")
