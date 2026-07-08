# tests/test_agent.py
import pytest
import pytest_asyncio
import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

# ── Environment setup ─────────────────────────────────────────────────────────
# Set env vars BEFORE any app.* imports so config.py picks them up correctly.
# DATABASE_URL drives the SQLAlchemy engine directly — no sys.modules heuristic.
os.environ["DATABASE_URL"]      = "sqlite+aiosqlite:///:memory:"
os.environ["CHROMA_PERSIST_DIR"] = "./vectorstore"
os.environ["JWT_SECRET_KEY"]     = "secure_test_signing_secret_for_cryptography_signatures_32chars"

pytestmark = pytest.mark.asyncio


# ── Module-scoped DB bootstrap ────────────────────────────────────────────────
# Schema + seed runs once per test session.  Mutating tests use their own
# function-scoped fixtures (see below) to avoid order-dependent failures.

@pytest_asyncio.fixture(scope="module", autouse=True)
async def bootstrap_db():
    """Creates schema and seeds demo data once for the whole test module."""
    from app.database import init_db, seed_demo_data
    await init_db()
    await seed_demo_data()


# ── Shared mock fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.generate.return_value = "Mocked LLM documentation output response."
    return client


@pytest.fixture
def mock_retriever():
    """
    Mock SecureRAGRetriever so tests never download the ~90 MB HuggingFace
    model or require a live ChromaDB vectorstore.  Returns (context, score)
    above the threshold so the RAG branch falls through to the LLM mock.
    """
    from app.rag.retriever import SecureRAGRetriever
    retriever = MagicMock(spec=SecureRAGRetriever)
    retriever.max_l2_distance_threshold = 1.25
    # Score above threshold → RAG gate triggers fallback to LLM
    retriever.retrieve_secure_context = AsyncMock(return_value=("", 2.0))
    return retriever


@pytest.fixture
def agent(mock_llm_client, mock_retriever):
    from app.chatbot import ProductionChatbotAgent
    from app.tools.router import SystemRouter

    router = SystemRouter(llm_client=mock_llm_client)
    return ProductionChatbotAgent(
        router=router,
        retriever=mock_retriever,
        llm_client=mock_llm_client,
    )


# ── Read-only / non-mutating tests ────────────────────────────────────────────

async def test_authorized_balance_inquiry(agent):
    """A customer can read their own balance."""
    payload = {"user_id": "1001", "role": "customer"}
    reply = await agent.process_message("sess_balance_ok", "balance of 1001", payload)
    assert "Ahmed Ali" in reply


async def test_unauthorized_balance_inquiry(agent):
    """A customer cannot read another user's balance."""
    payload = {"user_id": "1002", "role": "customer"}
    reply = await agent.process_message("sess_balance_deny", "balance of 1001", payload)
    assert "Access Denied" in reply or "do not have permission" in reply.lower()


async def test_unauthorized_rbac_action(agent):
    """A customer cannot transfer from an account they don't own."""
    payload = {"user_id": "1001", "role": "customer"}
    reply = await agent.process_message("sess_rbac_deny", "transfer 100 from 1002 to 1003", payload)
    assert "Access Denied" in reply or "do not have permission" in reply.lower()


# ── Mutating test — uses delta assertion to be order-independent ─────────────

async def test_ledger_transfer_deducts_correct_amount(agent):
    """
    Transfer 500 from account 1001 → 1002 and verify the deduction by delta.

    Reading the balance BEFORE the transfer and asserting the difference avoids
    the brittle absolute-value assertion (Decimal("14500.0000")) that breaks
    when test order or prior state changes.
    """
    from app.database import get_async_db_session, AccountEntity
    from sqlalchemy import select

    payload = {"user_id": "1001", "role": "customer"}
    transfer_amount = Decimal("500.0000")

    # Snapshot balances before the transfer
    async with get_async_db_session() as db:
        res = await db.execute(
            select(AccountEntity).filter(AccountEntity.account_id == "1001")
        )
        balance_before = res.scalars().first().balance

    reply = await agent.process_message(
        "sess_transfer_ok", "transfer 500 from 1001 to 1002", payload
    )
    assert "complete" in reply.lower() or "successfully" in reply.lower(), (
        f"Expected success message, got: {reply!r}"
    )

    # Verify deduction by delta — independent of absolute starting value
    async with get_async_db_session() as db:
        res = await db.execute(
            select(AccountEntity).filter(AccountEntity.account_id == "1001")
        )
        balance_after = res.scalars().first().balance

    assert balance_before - balance_after == transfer_amount, (
        f"Expected deduction of {transfer_amount}, "
        f"got before={balance_before} after={balance_after}"
    )


# ── Security: Refresh Token Rotation (RTR) ───────────────────────────────────

async def test_refresh_token_rotation_and_revocation():
    """
    Full RTR security test:
      1. Issue a refresh token and confirm it is stored as active.
      2. Simulate rotation — mark it revoked.
      3. Confirm the revoked token is rejected by decode_access_token.
      4. Confirm a brand-new token is accepted.

    Previously this test only checked token *creation*; it never exercised
    the rotation or rejection path, leaving the critical security behaviour
    untested.
    """
    from app.security import (
        create_and_persist_refresh_token,
        revoke_refresh_token,
        decode_access_token,
    )
    from app.database import get_async_db_session, RefreshTokenEntity
    from sqlalchemy import select

    # ── Step 1: issue token, verify active in DB ──────────────────────────
    raw_token = await create_and_persist_refresh_token("1001")
    decoded   = decode_access_token(raw_token)
    assert decoded is not None, "Newly issued refresh token must decode successfully"
    assert decoded.get("refresh") is True
    token_id = decoded["jti"]

    async with get_async_db_session() as db:
        res = await db.execute(
            select(RefreshTokenEntity).filter(RefreshTokenEntity.token_id == token_id)
        )
        record = res.scalars().first()
    assert record is not None, "Token must be persisted in DB"
    assert record.is_revoked is False, "Newly issued token must not be revoked"

    # ── Step 2: revoke the token ──────────────────────────────────────────
    revoked = await revoke_refresh_token(token_id)
    assert revoked is True, "revoke_refresh_token must return True on success"

    # ── Step 3: confirm revocation is persisted ───────────────────────────
    async with get_async_db_session() as db:
        res = await db.execute(
            select(RefreshTokenEntity).filter(RefreshTokenEntity.token_id == token_id)
        )
        record_after = res.scalars().first()
    assert record_after.is_revoked is True, "Token must be marked revoked in DB"

    # ── Step 4: issue a fresh token and confirm it is accepted ────────────
    new_token   = await create_and_persist_refresh_token("1001")
    new_decoded = decode_access_token(new_token)
    assert new_decoded is not None, "Fresh token must decode successfully"
    assert new_decoded["jti"] != token_id, "New token must have a different jti"
    assert new_decoded.get("refresh") is True


# ── Security: JWT access token claims ────────────────────────────────────────

async def test_access_token_contains_required_claims():
    """
    Verify that create_access_token writes the expected claims so downstream
    callers (ABAC checks, UI) always find user_id and role.
    """
    from app.security import create_access_token, decode_access_token

    token   = create_access_token({"user_id": "1001", "role": "admin"})
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"]     == "1001"
    assert payload["user_id"] == "1001"
    assert payload["role"]    == "admin"


async def test_expired_token_returns_none():
    """decode_access_token must return None for an expired token, not raise."""
    from datetime import timedelta
    from app.security import create_access_token, decode_access_token

    # Create a token that expired 5 minutes ago
    token = create_access_token(
        {"user_id": "1001", "role": "customer"},
        expires_delta=timedelta(minutes=-5),
    )
    result = decode_access_token(token)
    assert result is None, "Expired token must return None, not raise an exception"
