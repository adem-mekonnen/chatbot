# app/tools/registry.py
import logging
from decimal import Decimal
from typing import List, Type
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.database import get_async_db_session, db_write_lock, AccountEntity
from app.security import check_authorization
from app.tools.base import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger("enterprise-agent")

# ── Parameter schemas ────────────────────────────────────────────────────────

class BalanceSchema(BaseModel):
    account_id: str = Field(..., min_length=3, max_length=10)  # Support both usernames and numeric IDs

class TransferSchema(BaseModel):
    from_account: str = Field(..., min_length=3, max_length=10)  # Support both formats
    to_account:   str = Field(..., min_length=3, max_length=10)  # Support both formats
    amount: Decimal   = Field(..., gt=Decimal("0.0000"))

class RAGFallbackSchema(BaseModel):
    query: str = Field(..., min_length=1)

# ── Tool implementations ─────────────────────────────────────────────────────

class BankingBalanceTool(BaseTool):
    @property
    def name(self) -> str: return "get_balance"
    @property
    def required_action(self) -> str: return "VIEW_BALANCE_OWN"
    @property
    def description(self) -> str: return "Fetch balance details for an Account ID."
    @property
    def deterministic_patterns(self) -> List[str]:
        return [
            r"balance\s+(?:of|for)?\s*(?P<account_id>\d{4})",  # Numeric IDs like 1001
            r"balance\s+(?:of|for)?\s*(?P<account_id>[a-zA-Z]+)",  # Username IDs like alice, bob
        ]
    @property
    def schema(self) -> Type[BaseModel]: return BalanceSchema

    async def execute(self, user_payload: dict, parameters: BalanceSchema) -> ToolResult:
        acc_id = parameters.account_id
        user_id = user_payload.get("user_id")
        role = user_payload.get("role", "customer")
        
        logger.debug(f"Balance query: user={user_id}, role={role}, target_account={acc_id}")
        
        # Check if user is accessing their own account or if they have cross-user permissions
        is_own_account = str(user_id) == str(acc_id)
        required_permission = "VIEW_BALANCE_OWN" if is_own_account else "VIEW_BALANCE_ANY"
        
        logger.debug(f"Required permission: {required_permission}")
        
        if not check_authorization(user_payload, required_permission, acc_id):
            logger.warning(f"Access denied: user {user_id} cannot view balance for account {acc_id}")
            return ToolResult(
                status=ToolStatus.FORBIDDEN,
                message="Access Denied: You do not have permission to view this account.",
            )

        async with get_async_db_session() as db:
            res = await db.execute(
                select(AccountEntity).filter(AccountEntity.account_id == acc_id)
            )
            acc = res.scalars().first()
            if not acc:
                logger.warning(f"Account not found: {acc_id}")
                return ToolResult(
                    status=ToolStatus.NOT_FOUND,
                    message=f"Account ID '{acc_id}' is not registered.",
                )
            
            logger.info(f"Balance query successful: user {user_id} accessed account {acc_id} balance")
            return ToolResult(
                status=ToolStatus.SUCCESS,
                message=f"Current balance for {acc.name}: {acc.balance} {acc.currency}.",
            )


class BankingTransferTool(BaseTool):
    @property
    def name(self) -> str: return "transfer_funds"
    @property
    def required_action(self) -> str: return "TRANSFER_OWN"
    @property
    def description(self) -> str: return "Execute secure fund transfers."
    @property
    def deterministic_patterns(self) -> List[str]:
        return [
            r"transfer\s+(?P<amount>\d+(?:\.\d+)?)\s+"
            r"(?:from)?\s*(?P<from_account>\d{4}|\w+)\s+(?:to)?\s*(?P<to_account>\d{4}|\w+)"
        ]
    @property
    def schema(self) -> Type[BaseModel]: return TransferSchema

    async def execute(self, user_payload: dict, parameters: TransferSchema) -> ToolResult:
        from_acc = parameters.from_account
        to_acc   = parameters.to_account
        amount   = parameters.amount

        if not check_authorization(user_payload, self.required_action, from_acc):
            return ToolResult(
                status=ToolStatus.FORBIDDEN,
                message="Access Denied: You do not have permission to transfer from this account.",
            )

        if from_acc == to_acc:
            return ToolResult(
                status=ToolStatus.REJECTED,
                message="Transfer rejected: source and destination accounts are the same.",
            )

        async with get_async_db_session() as db:
            async with db_write_lock():
                try:
                    sender_res = await db.execute(
                        select(AccountEntity)
                        .filter(AccountEntity.account_id == from_acc)
                        .with_for_update()
                    )
                    recipient_res = await db.execute(
                        select(AccountEntity)
                        .filter(AccountEntity.account_id == to_acc)
                        .with_for_update()
                    )

                    sender    = sender_res.scalars().first()
                    recipient = recipient_res.scalars().first()

                    if not sender or not recipient:
                        return ToolResult(
                            status=ToolStatus.NOT_FOUND,
                            message="Transfer rejected: invalid source or destination account.",
                        )

                    sender_balance = Decimal(str(sender.balance))
                    tx_amount      = Decimal(str(amount))

                    if sender_balance < tx_amount:
                        return ToolResult(
                            status=ToolStatus.REJECTED,
                            message=(
                                f"Transfer rejected: insufficient funds. "
                                f"Available balance is {sender_balance} {sender.currency}."
                            ),
                        )

                    # Cache currency before commit — the ORM object becomes
                    # detached after the session closes.
                    sender_currency = sender.currency

                    sender.balance    = sender_balance - tx_amount
                    recipient.balance = Decimal(str(recipient.balance)) + tx_amount
                    await db.commit()

                except Exception as err:
                    await db.rollback()
                    raise err

        return ToolResult(
            status=ToolStatus.SUCCESS,
            message=f"Transfer complete: {amount} {sender_currency} sent to account {to_acc}.",
        )


class RAGFallbackTool(BaseTool):
    """
    Sentinel tool — signals the chatbot to run the RAG pipeline.
    Any authenticated user may query the policy knowledge base.
    """
    @property
    def name(self) -> str: return "rag_fallback"
    @property
    def required_action(self) -> str: return "VIEW_POLICY_DOCS"
    @property
    def description(self) -> str: return "Retrieve policy manuals and HR documentation."
    @property
    def deterministic_patterns(self) -> List[str]: return []
    @property
    def schema(self) -> Type[BaseModel]: return RAGFallbackSchema

    async def execute(self, user_payload: dict, parameters: RAGFallbackSchema) -> ToolResult:
        # Execution is handled entirely by the chatbot's RAG branch.
        # This tool is a routing marker only.
        return ToolResult(status=ToolStatus.SUCCESS, message="")
