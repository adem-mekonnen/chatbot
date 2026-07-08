# app/main.py
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from collections import OrderedDict
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text

from app.config import settings
from app.database import init_db, get_async_db_session, RefreshTokenEntity, UserEntity
from app.security import (
    decode_access_token,
    create_access_token,
    create_and_persist_refresh_token,
    revoke_refresh_token,
    authenticate_user_credentials,
    sanitize_user_input,
)
from app.logger import metrics_collector

logger = logging.getLogger("enterprise-agent")

# ─────────────────────────────────────────────────────────────────────────────
# Rate limiter
# ─────────────────────────────────────────────────────────────────────────────

class ExpiringRateLimiter:
    """
    Async sliding-window rate limiter backed by an OrderedDict for O(1) eviction.

    Uses asyncio.Lock (not threading.Lock) so that awaiting the lock in an
    async middleware never blocks the event loop thread.

    The OrderedDict maintains insertion order; the oldest entry is always
    at the front — eviction is O(1) via popitem(last=False).
    """

    def __init__(self, limit: int = 30, window_secs: int = 60, max_ips: int = 10_000):
        self.limit       = limit
        self.window_secs = window_secs
        self.max_ips     = max_ips
        self._logs: OrderedDict[str, list] = OrderedDict()
        self._lock       = asyncio.Lock()

    async def is_rate_limited(self, ip: str) -> bool:
        curr_time = time.time()
        async with self._lock:
            # Evict the oldest tracked IP to keep memory bounded — O(1).
            if len(self._logs) >= self.max_ips and ip not in self._logs:
                self._logs.popitem(last=False)

            if ip not in self._logs:
                self._logs[ip] = []
            else:
                # Move to end so recently-active IPs are not evicted first.
                self._logs.move_to_end(ip)

            # Slide the window: discard timestamps older than window_secs.
            self._logs[ip] = [t for t in self._logs[ip] if curr_time - t <= self.window_secs]

            if len(self._logs[ip]) >= self.limit:
                return True

            self._logs[ip].append(curr_time)
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — replaces deprecated @app.on_event("startup")
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Enhanced startup and shutdown with performance optimizations and connection warming.
    """
    startup_start_time = time.time()
    
    # Fail fast before accepting any traffic.
    settings.validate()

    # Lazy imports keep module-level import side-effects out of test collection.
    from app.llm.client import PluggableLLMClient
    from app.rag.retriever import SecureRAGRetriever
    from app.tools.router import SystemRouter
    from app.chatbot import ProductionChatbotAgent
    from app.database import warm_connection_pool

    logger.info("Starting application initialization...")

    # Initialize database and warm connection pool
    await init_db()
    
    # Warm up database connections
    try:
        await warm_connection_pool()
        logger.info("Database connection pool warmed successfully")
    except Exception as e:
        logger.error(f"Failed to warm connection pool: {e}")

    logger.warning(
        "Metrics collector is in-memory only — counters reset on restart. "
        "Push to a Prometheus Pushgateway for durable metrics."
    )

    # Initialize components with progress logging
    logger.info("Initializing LLM client...")
    llm_client = PluggableLLMClient()
    
    logger.info("Initializing RAG retriever...")
    retriever = SecureRAGRetriever()
    
    logger.info("Initializing system router...")
    router = SystemRouter(llm_client=llm_client)
    
    logger.info("Initializing chatbot agent...")
    agent = ProductionChatbotAgent(
        router=router, retriever=retriever, llm_client=llm_client
    )

    # Store on app.state so endpoint dependencies can retrieve them.
    app.state.llm_client = llm_client
    app.state.retriever = retriever
    app.state.router = router
    app.state.agent = agent

    # Pre-warm critical components
    try:
        logger.info("Pre-warming system components...")
        
        # Pre-warm LLM client with health check
        if hasattr(llm_client, '_get_ollama_health_status'):
            health_ok = await llm_client._get_ollama_health_status()
            logger.info(f"LLM health check: {'OK' if health_ok else 'FAILED'}")
        
        # Pre-warm RAG system with a test query
        if retriever.vectorstore:
            test_result = await retriever.retrieve_secure_context("system test query")
            logger.info(f"RAG system test: {'OK' if test_result else 'No results'}")
        
    except Exception as e:
        logger.warning(f"Component pre-warming failed (non-critical): {e}")

    startup_time = time.time() - startup_start_time
    logger.info(f"Application startup complete in {startup_time:.2f} seconds")
    
    # Record startup metrics
    metrics_collector.histogram("app_startup_duration", startup_time)
    metrics_collector.increment("app_starts_total")
    
    yield
    
    # Shutdown hook
    logger.info("Starting application shutdown...")
    
    # Add any cleanup (connection pool drain, etc.) here
    try:
        # Graceful shutdown of thread pools if needed
        from app.rag.retriever import _executor
        _executor.shutdown(wait=True, timeout=10.0)
        logger.info("Thread pools shut down gracefully")
    except Exception as e:
        logger.warning(f"Shutdown cleanup warning: {e}")
    
    logger.info("Application shutdown complete.")


# ─────────────────────────────────────────────────────────────────────────────
# App + middleware
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Production-Secured AI Agent API", lifespan=lifespan)

limiter = ExpiringRateLimiter()


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if await limiter.is_rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait and try again."},
        )
    return await call_next(request)


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str = Field(..., max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=64,
                            description="Client-generated unique session identifier.")
    # bypass_rag_gate is intentionally NOT exposed in the public API.
    # The compliance gate bypass is a server-side decision derived from the
    # authenticated user's role — callers cannot request it directly.

    @field_validator("session_id")
    @classmethod
    def session_id_must_not_be_default(cls, v: str) -> str:
        if v.strip().lower() in ("production_default", "default", ""):
            raise ValueError(
                "session_id must be a unique client-generated identifier, "
                "not a placeholder value."
            )
        return v


class TokenRequest(BaseModel):
    username: str = Field(..., description="Employee / user ID")
    password: str = Field(..., description="Credential string")


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ─────────────────────────────────────────────────────────────────────────────
# Dependency providers
# ─────────────────────────────────────────────────────────────────────────────

def get_agent(request: Request):
    return request.app.state.agent

def get_llm_client(request: Request):
    return request.app.state.llm_client


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication token required.")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token header format.")

    payload = decode_access_token(parts[1])
    if not payload or payload.get("refresh") is True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Access token is expired or invalid.")

    # Normalise: always expose 'user_id' regardless of token vintage.
    if "user_id" not in payload:
        payload["user_id"] = payload.get("sub")
    return payload


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that restricts an endpoint to admin-role users only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin role required.")
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """
    Lightweight liveness probe used by the Docker HEALTHCHECK and
    Kubernetes/ECS readiness checks.  Returns 200 as long as the
    process is running and the event loop is responsive.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health/detailed", dependencies=[Depends(require_admin)])
async def detailed_health_check(request: Request):
    """
    Comprehensive health check for admin users - checks all critical components.
    """
    start_time = time.time()
    health_status = {
        "overall": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {}
    }
    
    # Check database connectivity
    try:
        async with get_async_db_session() as db:
            await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        health_status["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["overall"] = "unhealthy"
    
    # Check LLM service
    try:
        llm_client = request.app.state.llm_client
        llm_healthy = await llm_client._get_ollama_health_status()
        health_status["components"]["llm"] = {
            "status": "healthy" if llm_healthy else "degraded",
            "ollama_available": llm_healthy,
            "fallback_available": bool(settings.hf_token)
        }
        if not llm_healthy and not settings.hf_token:
            health_status["overall"] = "degraded"
    except Exception as e:
        health_status["components"]["llm"] = {"status": "unhealthy", "error": str(e)}
        health_status["overall"] = "unhealthy"
    
    # Check RAG system
    try:
        retriever = request.app.state.retriever
        rag_available = retriever.vectorstore is not None
        health_status["components"]["rag"] = {
            "status": "healthy" if rag_available else "unhealthy",
            "vectorstore_available": rag_available
        }
        if not rag_available:
            health_status["overall"] = "degraded"
    except Exception as e:
        health_status["components"]["rag"] = {"status": "unhealthy", "error": str(e)}
        health_status["overall"] = "degraded"
    
    # Add performance metrics
    health_status["performance"] = {
        "check_duration_ms": round((time.time() - start_time) * 1000, 2),
        "memory_cache_sizes": {
            "rag_cache": len(getattr(request.app.state.retriever, '_query_cache', {})),
            "auth_cache": len(globals().get('_auth_cache', {}))
        }
    }
    
    status_code = 200 if health_status["overall"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/metrics", dependencies=[Depends(require_admin)])
def get_metrics_endpoint():
    """
    Prometheus scraping endpoint — admin only.
    Returns text/plain; version=0.0.4 as required by the exposition format.
    """
    return PlainTextResponse(
        content=metrics_collector.export_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/token")
async def acquire_tokens(payload: TokenRequest):
    """Enhanced token endpoint with performance monitoring and better error handling."""
    start_time = time.time()
    
    logger.info(f"Authentication attempt for user: {payload.username}")
    
    try:
        user = await authenticate_user_credentials(payload.username, payload.password)
        elapsed = time.time() - start_time
        
        if not user:
            # Log failed authentication
            metrics_collector.increment("auth_failures")
            logger.warning(f"Authentication failed for user {payload.username} in {elapsed:.3f}s")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials. Please check your username and password."
            )
        
        # Generate tokens
        access_token = create_access_token(user)
        refresh_token = await create_and_persist_refresh_token(payload.username)
        
        # Log successful authentication
        metrics_collector.increment("auth_successes")
        metrics_collector.histogram("auth_request_duration", elapsed)
        
        logger.info(f"Authentication successful for user {payload.username} (role: {user.get('role')}) in {elapsed:.3f}s")
        
        return {
            "access_token": access_token, 
            "refresh_token": refresh_token, 
            "token_type": "bearer",
            "user_role": user.get("role"),
            "expires_in": settings.access_token_expire_minutes * 60  # seconds
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 401)
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        
        # Log unexpected errors
        metrics_collector.increment("auth_errors")
        logger.error(f"Authentication system error for user {payload.username} after {elapsed:.3f}s: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable. Please try again in a moment."
        )


@app.post("/refresh")
async def refresh_access_token(payload: RefreshRequest):
    """Issues a new access token via Refresh Token Rotation (RTR)."""
    decoded = decode_access_token(payload.refresh_token)
    if not decoded or decoded.get("refresh") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid refresh token.")

    token_id = decoded.get("jti")
    async with get_async_db_session() as db:
        res = await db.execute(
            select(RefreshTokenEntity).filter(
                RefreshTokenEntity.token_id  == token_id,
                RefreshTokenEntity.is_revoked == False,
                RefreshTokenEntity.expires_at > datetime.now(timezone.utc),
            )
        )
        token_record = res.scalars().first()
        if not token_record:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Refresh token is revoked or expired.")

        token_record.is_revoked = True
        await db.commit()

        user_id  = decoded.get("sub")
        user_res = await db.execute(
            select(UserEntity).filter(UserEntity.user_id == user_id)
        )
        user = user_res.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="User not found.")

        new_access  = create_access_token({"user_id": user_id, "role": user.role})
        new_refresh = await create_and_persist_refresh_token(user_id)
        return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@app.post("/logout")
async def logout(payload: LogoutRequest):
    """Revokes the refresh token, terminating the session."""
    decoded = decode_access_token(payload.refresh_token)
    if not decoded or decoded.get("refresh") is not True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid refresh token structure.")
    revoked = await revoke_refresh_token(decoded.get("jti"))
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Token not found or already revoked.")
    return {"status": "success", "message": "Logged out successfully."}


@app.post("/chat")
async def run_secure_chat(
    payload:    ChatRequest,
    request:    Request,
    user:       dict = Depends(get_current_user),
    agent=Depends(get_agent),
):
    """
    Enhanced main chat endpoint with performance monitoring and error handling.
    """
    start_time = time.time()
    correlation_id = f"chat-{int(start_time * 1000)}-{user.get('user_id', 'unknown')}"
    
    logger.info(f"Chat request started", extra={
        "correlation_id": correlation_id,
        "user_id": user.get('user_id'),
        "session_id": payload.session_id,
        "message_length": len(payload.message)
    })
    
    try:
        # Determine bypass based on user role (server-side decision)
        bypass = user.get("role") == "admin"
        
        response = await agent.process_message(
            session_id=payload.session_id,
            raw_message=payload.message,
            user_payload=user,
            bypass_rag_gate=bypass,
        )
        
        elapsed = time.time() - start_time
        
        # Log success metrics
        metrics_collector.histogram("chat_request_duration", elapsed)
        metrics_collector.increment("chat_requests_success")
        
        logger.info(f"Chat request completed successfully in {elapsed:.3f}s", extra={
            "correlation_id": correlation_id,
            "response_length": len(response),
            "elapsed": elapsed
        })
        
        return {
            "response": response,
            "correlation_id": correlation_id,
            "processing_time": f"{elapsed:.3f}s"
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        
        # Log error metrics
        metrics_collector.increment("chat_requests_error")
        metrics_collector.histogram("chat_request_error_duration", elapsed)
        
        logger.error(f"Chat request failed after {elapsed:.3f}s: {str(e)}", extra={
            "correlation_id": correlation_id,
            "error": str(e),
            "elapsed": elapsed
        })
        
        # Return user-friendly error with correlation ID for support
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
                "correlation_id": correlation_id,
                "support_message": "If this issue persists, please contact IT support with this correlation ID."
            }
        )


@app.post("/chat/stream")
async def run_secure_chat_stream(
    payload: ChatRequest,
    request: Request,
    user:    dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
):
    """
    Streaming chat endpoint.

    Applies the same input sanitization as the standard /chat endpoint.
    Streaming bypasses the full agent pipeline (RAG, tool routing, audit log)
    by design — it is intended for direct LLM interaction only.
    """
    safe_message = sanitize_user_input(payload.message)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for chunk in llm.generate_stream(safe_message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
