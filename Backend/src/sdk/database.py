# ═══════════════════════════════════════════════════════════════
# fte_sdk / database.py
#
# PURPOSE: SQLAlchemy async engine setup + session management.
#          Har agent apna DB session yahin se leta hai.
#          init_db() tables create karta hai startup pe.
#
# USED BY: ALL agents + backend
# EXPORTS: engine, async_session_factory, get_db(), init_db(), Base
# ═══════════════════════════════════════════════════════════════

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.sdk.config import get_settings

settings = get_settings()

# ─── Engine (Async) ───────────────────────────────────────────
# SQLAlchemy async engine — connects to PostgreSQL via asyncpg.
# echo=DEBUG logs all SQL queries (dev only).

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# ─── Session Factory ──────────────────────────────────────────
# Creates new AsyncSession instances. expire_on_commit=False
# lets us access model attributes after commit.

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ─── Base (Declarative Base) ──────────────────────────────────
# All ORM models inherit from this. SQLAlchemy uses this to
# discover tables for CREATE TABLE / migrations.

class Base(DeclarativeBase):
    pass


# ─── get_db() (FastAPI Dependency) ────────────────────────────
# Usage in FastAPI: `async def handler(db: AsyncSession = Depends(get_db))`
# Yields a session, auto-closes on request completion.

async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# ─── init_db() (Startup) ──────────────────────────────────────
# Creates all tables defined in models. Called on service startup.
# In production, use Alembic migrations instead.

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
