# ═══════════════════════════════════════════════════════════════
# fte_sdk / models / base.py
#
# PURPOSE: Core commerce models — MULTI-PLATFORM now.
#          Har e-commerce platform (Shopify, WooCommerce, Amazon,
#          Daraz, BigCommerce) ke liye common schema.
#
#          Backward compatible: purane shopify_id/shop_domain
#          columns abhi bhi exist karte hain (deprecated).
#          Naye code mein platform_product_id etc. use karo.
#
# USED BY: inventory_sync, customer_support, analytics_insights,
#          backend API, ALL agents
# ═══════════════════════════════════════════════════════════════

import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean,
    ForeignKey, DateTime, JSON, func,
)
from sqlalchemy.orm import relationship

from src.sdk.database import Base


# ─── Store ─────────────────────────────────────────────────────
# Connected e-commerce store. Stores OAuth access token.
# Platform-agnostic: aisle field batata hai yeh Shopify hai ya
# WooCommerce ya Amazon ya Daraz.
#
# Backward compat: shop_name / shop_domain deprecated but exist.

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── Ownership ───────────────────────────────────────────
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Owner (auth domain User)

    # ─── Multi-Platform Fields (NEW) ─────────────────────────
    platform = Column(String(50), nullable=False, default="shopify", index=True)
    platform_store_id = Column(String(255), nullable=True)   # shop_domain, store_hash, etc.
    name = Column(String(255), nullable=False, default="")   # Human-readable store name
    refresh_token = Column(String(512), default="")
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # ─── Legacy Shopify Fields (DEPRECATED) ──────────────────
    shop_name = Column(String(255), nullable=False, default="", index=True)
    shop_domain = Column(String(255), nullable=True, unique=True)

    # ─── Common ──────────────────────────────────────────────
    access_token = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="store", cascade="all, delete-orphan")


# ─── Product ───────────────────────────────────────────────────
# Product synced from any e-commerce platform.
# platform_product_id = unique ID from the source platform.
# extra_data = JSON blob for platform-specific fields.

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)

    # ─── Multi-Platform Fields (NEW) ─────────────────────────
    platform_product_id = Column(String(255), nullable=True, index=True)

    # ─── Legacy Shopify Fields (DEPRECATED) ──────────────────
    shopify_id = Column(Integer, nullable=True, unique=True)

    # ─── Common ──────────────────────────────────────────────
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    vendor = Column(String(255), default="")
    product_type = Column(String(255), default="")
    status = Column(String(50), default="active")
    image_url = Column(String(512), default="")
    extra_data = Column(JSON, default={})          # Platform-specific metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    store = relationship("Store", back_populates="products")
    variants = relationship("Variant", back_populates="product", cascade="all, delete-orphan")


# ─── Variant ───────────────────────────────────────────────────
# Product variant — SKU, price, inventory tracking.
# LowStockAlert references this when stock drops below threshold.

class Variant(Base):
    __tablename__ = "variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # ─── Multi-Platform Fields (NEW) ─────────────────────────
    platform_variant_id = Column(String(255), nullable=True, index=True)

    # ─── Legacy Shopify Fields (DEPRECATED) ──────────────────
    shopify_id = Column(Integer, nullable=True, unique=True)

    # ─── Common ──────────────────────────────────────────────
    title = Column(String(255), nullable=False)
    sku = Column(String(100), default="")
    price = Column(Numeric(12, 2), default=0)
    compare_at_price = Column(Numeric(12, 2), nullable=True)
    inventory_quantity = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    extra_data = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="variants")
    order_items = relationship("OrderItem", back_populates="variant")


# ─── Order ─────────────────────────────────────────────────────
# Customer order from e-commerce platform.
# Used by customer_support, analytics_insights.

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)

    # ─── Multi-Platform Fields (NEW) ─────────────────────────
    platform_order_id = Column(String(255), nullable=True, index=True)

    # ─── Legacy Shopify Fields (DEPRECATED) ──────────────────
    shopify_id = Column(Integer, nullable=True, unique=True)

    # ─── Common ──────────────────────────────────────────────
    order_number = Column(String(50), nullable=False)
    customer_email = Column(String(255), default="")
    total_price = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), default="USD")
    financial_status = Column(String(50), default="pending")
    fulfillment_status = Column(String(50), nullable=True)
    ordered_at = Column(DateTime(timezone=True), nullable=False)
    extra_data = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    store = relationship("Store", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# ─── OrderItem ─────────────────────────────────────────────────
# Line item in an order — which variant + quantity + price paid.

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Numeric(12, 2), default=0)

    order = relationship("Order", back_populates="items")
    variant = relationship("Variant", back_populates="order_items")


# ─── LowStockAlert (Cross-cutting) ─────────────────────────────
# Created by inventory_sync when inventory drops below threshold.
# Read by analytics_insights for reporting.

class LowStockAlert(Base):
    __tablename__ = "low_stock_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    product_title = Column(String(255), default="")
    variant_title = Column(String(255), default="")
    sku = Column(String(100), default="")
    current_stock = Column(Integer, default=0)
    threshold = Column(Integer, default=10)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
