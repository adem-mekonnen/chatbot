# app/chatbot.py
import uuid
import time
import logging
from sqlalchemy import select
from app.database import get_async_db_session, ChatHistory, AuditLog
from app.security import sanitize_user_input
from app.tools.router import SystemRouter
from app.tools.base import ToolResult, ToolStatus
from app.rag.retriever import SecureRAGRetriever
from app.llm.client import PluggableLLMClient
from app.logger import structured_logger, metrics_collector

logger = logging.getLogger("enterprise-agent")

# Roles permitted to request bypass_rag_gate=True (Strict Mode Override)
_GATE_BYPASS_ROLES = frozenset({"admin", "manager"})

class ProductionChatbotAgent:
    def __init__(self, router: SystemRouter, retriever: SecureRAGRetriever, llm_client: PluggableLLMClient):
        self.router = router
        self.retriever = retriever
        self.llm = llm_client

    async def process_message(self, session_id: str, raw_message: str, user_payload: dict, bypass_rag_gate: bool = False) -> str:
        start_time = time.time()
        correlation_id = str(uuid.uuid4())
        sanitized_msg = sanitize_user_input(raw_message)
        user_id = user_payload.get("user_id", "anonymous")
        role = user_payload.get("role", "customer")

        # ── 1. Context Loading (Sliding Window) ──────────────────────────────
        async with get_async_db_session() as db:
            db.add(ChatHistory(session_id=session_id, role="user", content=sanitized_msg))
            await db.commit()
            
            history_stmt = select(ChatHistory).filter(ChatHistory.session_id == session_id).order_by(ChatHistory.timestamp.desc()).limit(6)
            res = await db.execute(history_stmt)
            history_records = list(res.scalars().all())
            history_records.reverse()
            history_str = "\n".join(f"{h.role}: {h.content}" for h in history_records)

        # ── 2. Intent Routing ───────────────────────────────────────────────
        routing_decision = await self.router.determine_intent(sanitized_msg)
        tool_name = routing_decision.tool
        params = routing_decision.parameters
        agent_response = ""
        operation_status = ToolStatus.SUCCESS

        # ── Branch A: Execute Logic Tools (Balance/Transfer) ────────────────
        if tool_name in self.router.tools and tool_name != "rag_fallback":
            tool = self.router.tools[tool_name]
            try:
                validated_params = tool.schema(**params)
                result: ToolResult = await tool.execute(user_payload, validated_params)
                operation_status = result.status
                agent_response = result.message
            except Exception as err:
                operation_status = ToolStatus.VALIDATION_FAIL
                agent_response = f"I encountered an error processing that action: {err}"

        # ── Branch B: Intelligent RAG + General Knowledge ───────────────────
        else:
            # Search the Knowledge Base (PDFs)
            context, score = await self.retriever.retrieve_secure_context(sanitized_msg)
            
            # Decide if we use PDF Context or General Knowledge
            if context and score < self.retriever.max_l2_distance_threshold:
                # MODE: Verified Knowledge (RAG)
                tool_name = "rag_search"
                system_instruction = (
                    "You are an Enterprise AI Coordinator. Use the retrieved context below to answer accurately.\n"
                    "If the answer isn't in the context, say you don't know rather than guessing.\n"
                    f"CONTEXT:\n{context}\n\nHISTORY:\n{history_str}"
                )
            else:
                # MODE: General Assistant (Outside RAG)
                tool_name = "general_ai"
                system_instruction = (
                    "You are a professional Enterprise Assistant. The user is asking a question "
                    "outside of company policy documents. Answer politely using your general knowledge.\n"
                    "Disclaimer: Mention briefly if the answer is based on general knowledge and not internal policy.\n"
                    f"HISTORY:\n{history_str}"
                )

            agent_response = await self.llm.generate(sanitized_msg, system_context=system_instruction)

        # ── 3. Audit & History Logging ──────────────────────────────────────
        async with get_async_db_session() as db:
            latency_ms = int((time.time() - start_time) * 1000)
            db.add(AuditLog(
                user_id=user_id, session_id=session_id, correlation_id=correlation_id,
                action=tool_name, status=operation_status.value,
                details={"query": sanitized_msg, "latency": latency_ms}
            ))
            db.add(ChatHistory(session_id=session_id, role="assistant", content=agent_response))
            await db.commit()

        return agent_response