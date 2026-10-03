# ═══════════════════════════════════════════════════════════════
# fte_sdk / models / support.py
#
# PURPOSE: Customer support models — conversations, messages,
#          human handoff logging.
#
# USED BY: customer_support (chat, RAG, handoff)
# ═══════════════════════════════════════════════════════════════

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import relationship

from src.sdk.database import Base


# ─── Conversation ─────────────────────────────────────────────
# Customer support conversation thread.
# Links to product for RAG context. status tracks lifecycle.

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    customer_email = Column(String(255), default="")
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    status = Column(String(50), default="open")            # open | closed | handoff
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


# ─── Message ──────────────────────────────────────────────────
# Single message within a conversation.
# role = "customer" | "agent_bot" | "agent_human"

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)               # customer | agent_bot | agent_human
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


# ─── HandoffLog ──────────────────────────────────────────────
# Records when a conversation was escalated from bot → human.
# reason = why it was escalated. assigned_to = human agent ID.

class HandoffLog(Base):
    __tablename__ = "handoff_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    reason = Column(Text, default="")
    assigned_to = Column(String(255), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
