# app/main.py
import asyncio
import logging
import time
import os
from contextlib import asynccontextmanager
from collections import OrderedDict
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text

from app.config import settings
from app.database import init_db, get_async_db_session, RefreshTokenEntity, UserEntity, warm_connection_pool, seed_demo_data
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
    """Async sliding-window rate limiter with O(1) eviction."""
    def __init__(self, limit: int = 30, window_secs: int = 60, max_ips: int = 10_000):
        self.limit = limit
        self.window_secs = window_secs
        self.max_ips = max_ips
        self._logs: OrderedDict[str, list] = OrderedDict()
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, ip: str) -> bool:
        curr_time = time.time()
        async with self._lock:
            if len(self._logs) >= self.max_ips and ip not in self._logs:
                self._logs.popitem(last=False)
            if ip not in self._logs:
                self._logs[ip] = []
            else:
                self._logs.move_to_end(ip)
            self._logs[ip] = [t for t in self._logs[ip] if curr_time - t <= self.window_secs]
            if len(self._logs[ip]) >= self.limit:
                return True
            self._logs[ip].append(curr_time)
            return False

# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — Handles Startup and Shutdown
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    startup_start_time = time.time()
    settings.validate()

    from app.llm.client import PluggableLLMClient
    from app.rag.retriever import SecureRAGRetriever
    from app.tools.router import SystemRouter
    from app.chatbot import ProductionChatbotAgent

    logger.info("Initializing Enterprise AI Backend...")

    # 1. Initialize Database with Retry Logic (Crucial for Supabase Free Tier)
    db_initialized = False
    for attempt in range(3):
        try:
            await init_db()
            await warm_connection_pool()
            # Ensure admin user exists in the new Supabase DB
            await seed_demo_data()
            logger.info("Database connection and seeding successful.")
            db_initialized = True
            break
        except Exception as e:
            logger.warning(f"Database init attempt {attempt+1} failed: {e}. Retrying...")
            await asyncio.sleep(5)
    
    if not db_initialized:
        logger.error("COULD NOT CONNECT TO DATABASE. Shutting down.")
        raise RuntimeError("Database connection failed.")

    # 2. Initialize Agent Components
    llm_client = PluggableLLMClient()
    retriever = SecureRAGRetriever()
    router = SystemRouter(llm_client=llm_client)
    agent = ProductionChatbotAgent(router=router, retriever=retriever, llm_client=llm_client)

    app.state.llm_client = llm_client
    app.state.retriever = retriever
    app.state.agent = agent

    startup_time = time.time() - startup_start_time
    logger.info(f"Startup complete in {startup_time:.2f}s")
    metrics_collector.increment("app_starts_total")
    
    yield
    
    logger.info("Application shutting down...")

# ─────────────────────────────────────────────────────────────────────────────
# App Instance & Middleware
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Enterprise AI Agent API", version="1.0.0", lifespan=lifespan)

# 1. CORS Middleware - Allows your Streamlit UI to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your specific Render URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Server"] = "Enterprise-Secure-Agent"
    return response

# 3. Rate Limiting Middleware
limiter = ExpiringRateLimiter()
@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if await limiter.is_rate_limited(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests."})
    return await call_next(request)

# ─────────────────────────────────────────────────────────────────────────────
# Schemas & Dependencies
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=64)

    @field_validator("session_id")
    @classmethod
    def session_id_must_not_be_default(cls, v: str) -> str:
        if v.strip().lower() in ("default", "production_default", ""):
            raise ValueError("Provide a unique session identifier.")
        return v

class TokenRequest(BaseModel):
    username: str
    password: str

def get_agent(request: Request):
    return request.app.state.agent

def get_llm_client(request: Request):
    return request.app.state.llm_client

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Valid token required.")
    
    token = authorization.split()[1]
    payload = decode_access_token(token)
    if not payload or payload.get("refresh"):
        raise HTTPException(status_code=401, detail="Token invalid or expired.")
    
    if "user_id" not in payload:
        payload["user_id"] = payload.get("sub")
    return payload

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/token")
async def login(payload: TokenRequest):
    user = await authenticate_user_credentials(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    
    access_token = create_access_token(user)
    refresh_token = await create_and_persist_refresh_token(payload.username)
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        "role": user.get("role")
    }

@app.post("/chat")
async def chat_endpoint(
    payload: ChatRequest, 
    user: dict = Depends(get_current_user),
    agent = Depends(get_agent)
):
    try:
        # Admin bypass logic
        bypass = user.get("role") == "admin"
        
        response = await agent.process_message(
            session_id=payload.session_id,
            raw_message=payload.message,
            user_payload=user,
            bypass_rag_gate=bypass
        )
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="The AI service encountered an error.")

@app.get("/metrics")
def get_metrics(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return PlainTextResponse(metrics_collector.export_prometheus_format())