# app/database.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional  # kept for any future optional fields in ORM models
from sqlalchemy import Column, String, Integer, DateTime, Numeric, JSON, Boolean, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
from app.config import settings
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Use settings.database_url directly — it reads DATABASE_URL from the environment.
# Tests set DATABASE_URL=sqlite+aiosqlite:///:memory: before importing this module,
# so no sys.modules heuristic is needed (and that heuristic silently ignored the
# env var anyway).
db_url = settings.database_url

# ---------------------------------------------------------------------------
# Enhanced Engine Configuration with Connection Pooling
# ---------------------------------------------------------------------------

# SQLite requires check_same_thread=False when used with async drivers so that
# aiosqlite can hand the connection between threads during await points.
_connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

# Enhanced connection pooling for better performance
if db_url.startswith("sqlite"):
    # SQLite doesn't support connection pooling with aiosqlite
    _pool_kwargs = {}
else:
    _pool_kwargs = {
        "pool_size": 25,
        "max_overflow": 50,
        "pool_recycle": 300,  # 5 minutes
        "pool_timeout": 30,   # 30 seconds
    }

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
    **_pool_kwargs,
)

# Pre-warm connection pool on startup
async def warm_connection_pool():
    """Pre-warm the connection pool to reduce initial request latency"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection pool warmed successfully")
    except Exception as e:
        logger.error(f"Failed to warm connection pool: {e}")

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# ---------------------------------------------------------------------------
# ORM Entities
# ---------------------------------------------------------------------------

class UserEntity(Base):
    """Stores persistent credential hashes to eliminate run-time hash regeneration overhead."""
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)


class AccountEntity(Base):
    """Secure balance ledger table."""
    __tablename__ = "accounts"
    account_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    balance = Column(Numeric(precision=14, scale=4, asdecimal=True), nullable=False)
    currency = Column(String, default="ETB")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    # timezone-aware UTC timestamp (datetime.utcnow is deprecated in Python 3.12+)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    correlation_id = Column(String, index=True, nullable=False)
    user_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False)
    details = Column(JSON, nullable=True)


class RefreshTokenEntity(Base):
    """Stores valid refresh token signatures to support revocation and prevent replay attacks."""
    __tablename__ = "refresh_tokens"
    token_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# SQLite write-lock
# ---------------------------------------------------------------------------
# Created eagerly at module level so there is no race window between two
# coroutines both seeing None and creating separate lock instances.
# asyncio.Lock() is safe to create at import time in Python 3.10+.
_sqlite_write_lock: asyncio.Lock = asyncio.Lock()


@asynccontextmanager
async def db_write_lock():
    """Context manager that serialises SQLite writes with an asyncio lock.
    For PostgreSQL and other servers, the context is a no-op."""
    if db_url.startswith("sqlite"):
        async with _sqlite_write_lock:
            yield
    else:
        yield


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_async_db_session():
    """Yields a context-managed async database session.
    Rolls back automatically on any unhandled exception before closing."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Schema initialisation  (schema only — no seed data)
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Creates all ORM-mapped tables if they do not already exist.

    This function is intentionally limited to DDL.  Demo/seed data lives in
    seed_demo_data() and must be called explicitly from a one-off script or
    a controlled migration step — never from application startup in production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Demo seed  (DEV / CI only — never call from production startup)
# ---------------------------------------------------------------------------

async def seed_demo_data() -> None:
    """Inserts a minimal set of demo users and accounts for local development
    and CI tests.

    Passwords are read from environment variables so that even dev credentials
    are not hardcoded in source.  Falls back to obvious placeholder values that
    are intentionally weak and clearly dev-only.

    WARNING: Do NOT call this function from production startup code.
    Use Alembic data migrations for production seed data.
    """
    import os
    from sqlalchemy import select

    user_pw_1001 = os.getenv("SEED_PASSWORD_1001", "dev_password_ahmed")
    user_pw_1002 = os.getenv("SEED_PASSWORD_1002", "dev_password_sara")
    user_pw_admin = os.getenv("SEED_PASSWORD_ADMIN", "dev_password_admin")

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(UserEntity))
        if res.scalars().first() is not None:
            logger.info("seed_demo_data: users table is not empty — skipping seed.")
            return

        logger.warning(
            "seed_demo_data: seeding demo users and accounts. "
            "This should only run in development or CI environments."
        )
        session.add_all([
            UserEntity(user_id="1001", password_hash=pwd_context.hash(user_pw_1001), role="customer"),
            UserEntity(user_id="1002", password_hash=pwd_context.hash(user_pw_1002), role="customer"),
            UserEntity(user_id="admin", password_hash=pwd_context.hash(user_pw_admin), role="admin"),
        ])
        session.add_all([
            AccountEntity(account_id="1001", name="Ahmed Ali",      balance=15000.0000, currency="ETB"),
            AccountEntity(account_id="1002", name="Sara Mohammed",  balance=8200.0000,  currency="ETB"),
            AccountEntity(account_id="1003", name="Abebe Kebede",   balance=450.0000,   currency="ETB"),
        ])
        await session.commit()
