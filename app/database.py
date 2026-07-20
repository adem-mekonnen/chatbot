# app/database.py
import asyncio
import logging
import ssl
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Numeric, JSON, Boolean, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
from app.config import settings
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Use settings.database_url directly
db_url = settings.database_url

# ---------------------------------------------------------------------------
# Enhanced Engine Configuration with Supabase Pooler & SSL Fixes
# ---------------------------------------------------------------------------

if db_url.startswith("sqlite"):
    # SQLite logic for local development
    _connect_args = {"check_same_thread": False}
    _pool_kwargs = {}
else:
    # POSTGRES (SUPABASE TRANSACTION POOLER) LOGIC
    # 1. Create a permissive SSL context to fix Render's certificate error
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # 2. Configure connect_args for asyncpg
    # CRITICAL: statement_cache_size=0 is REQUIRED for Supabase Transaction Pooler
    _connect_args = {
        "ssl": ctx,
        "statement_cache_size": 0 
    } 
    
    # 3. Connection Pool settings optimized for Render Free Tier
    _pool_kwargs = {
        "pool_size": 10,
        "max_overflow": 5,
        "pool_recycle": 300,
        "pool_timeout": 30,
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
    """Stores user credentials and roles."""
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)


class AccountEntity(Base):
    """Stores user financial balances."""
    __tablename__ = "accounts"
    account_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    balance = Column(Numeric(precision=14, scale=4, asdecimal=True), nullable=False)
    currency = Column(String, default="ETB")


class ChatHistory(Base):
    """Stores conversation logs for RAG context."""
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """Stores security and action logs for compliance."""
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
    """Stores auth refresh tokens."""
    __tablename__ = "refresh_tokens"
    token_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

# ---------------------------------------------------------------------------
# Helper Contexts & Methods
# ---------------------------------------------------------------------------

_sqlite_write_lock: asyncio.Lock = asyncio.Lock()

@asynccontextmanager
async def db_write_lock():
    if db_url.startswith("sqlite"):
        async with _sqlite_write_lock:
            yield
    else:
        yield

@asynccontextmanager
async def get_async_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Creates tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_demo_data() -> None:
    """Seeds the database with admin and test accounts."""
    import os
    from sqlalchemy import select

    # Environment variable passwords (fallbacks used if not set)
    user_pw_1001 = os.getenv("SEED_PASSWORD_1001", "dev_password_ahmed")
    user_pw_1002 = os.getenv("SEED_PASSWORD_1002", "dev_password_sara")
    user_pw_admin = os.getenv("SEED_PASSWORD_ADMIN", "dev_password_admin")

    async with AsyncSessionLocal() as session:
        # Only seed if users table is empty
        res = await session.execute(select(UserEntity))
        if res.scalars().first() is not None:
            return

        logger.warning("seed_demo_data: seeding demo users and accounts.")
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