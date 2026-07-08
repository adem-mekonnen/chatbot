# app.py — Streamlit entry point (embedded backend, no HTTP API calls)
import sys
import os
import asyncio
import base64
import uuid
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Environment defaults
# Must be set BEFORE any app.* imports so config.py reads correct values.
# ─────────────────────────────────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL",    "sqlite+aiosqlite:///./enterprise_state.db")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./vectorstore")
os.environ.setdefault("CHROMA_COLLECTION",  "enterprise_docs")

# JWT_SECRET_KEY must be a fixed persistent secret — never generated at runtime.
# If it is absent, surface a clear error instead of silently creating a
# throwaway key that invalidates all tokens on every Streamlit restart.
if not os.environ.get("JWT_SECRET_KEY"):
    st.set_page_config(page_title="Configuration Error", page_icon="🚨")
    st.error(
        "**Configuration Error — application cannot start.**\n\n"
        "The `JWT_SECRET_KEY` environment variable is not set. "
        "Generate a strong secret and add it to your `.env` file:\n\n"
        "```\nJWT_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_urlsafe(48))\")\n```"
    )
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Top-level imports (after env is configured)
# ─────────────────────────────────────────────────────────────────────────────
from app.security import authenticate_user_credentials  # moved from inside the form block
from app.database import init_db
from app.chatbot import ProductionChatbotAgent

logger = logging.getLogger("enterprise-agent")

# ─────────────────────────────────────────────────────────────────────────────
# Async helper — safe for Streamlit's custom thread context
#
# Streamlit reruns the script from top to bottom on every user interaction.
# The standard asyncio.run() creates a new event loop each time, which
# conflicts with any already-running loop in the Streamlit thread.
#
# nest_asyncio patches the running loop to allow re-entrant calls, which is
# the approach recommended for Jupyter-like environments.  We install it once
# and then use asyncio.get_event_loop().run_until_complete() for all sync→async
# bridges throughout this file.
# ─────────────────────────────────────────────────────────────────────────────
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    st.warning(
        "`nest_asyncio` is not installed. Async calls from Streamlit may fail "
        "with 'This event loop is already running'. "
        "Install it with:  pip install nest_asyncio"
    )

def _run(coro):
    """Run a coroutine from synchronous Streamlit code, safely."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# ─────────────────────────────────────────────────────────────────────────────
# One-time startup — guarded by session state so it runs once per process,
# not on every Streamlit rerun triggered by a user interaction.
# ─────────────────────────────────────────────────────────────────────────────
if "app_initialised" not in st.session_state:
    _run(init_db())

    from app.llm.client import PluggableLLMClient
    from app.rag.retriever import SecureRAGRetriever
    from app.tools.router import SystemRouter

    llm       = PluggableLLMClient()
    router    = SystemRouter(llm_client=llm)
    retriever = SecureRAGRetriever()

    st.session_state.agent         = ProductionChatbotAgent(
        router=router, retriever=retriever, llm_client=llm
    )
    st.session_state.app_initialised = True
    logger.info("Streamlit app initialised: DB ready, agent loaded.")

# ─────────────────────────────────────────────────────────────────────────────
# Per-session state defaults
# ─────────────────────────────────────────────────────────────────────────────
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages = []

# ─────────────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call after imports)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ABC Inc. Assistant", page_icon="🏢", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# Logo helper
# ─────────────────────────────────────────────────────────────────────────────
def _get_logo_b64() -> str:
    try:
        with open("ui/abc_corporate_logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_logo_b64 = _get_logo_b64()
_logo_img = (
    f'<img src="data:image/png;base64,{_logo_b64}" '
    f'style="width:72px;height:72px;object-fit:contain;'
    f'display:block;margin:0 auto 20px auto;'
    f'border-radius:16px;box-shadow:0 8px 24px rgba(99,102,241,0.35);" />'
) if _logo_b64 else ""

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Outfit:wght@500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer { visibility: hidden; }
.stDeployButton { display: none !important; }

.stApp {
    background: radial-gradient(ellipse at 18% 8%, #1e1b4b 0%, #080d1a 45%, #0f172a 100%) !important;
    color: #e2e8f0 !important;
}

@keyframes fadeInUp {
    from { opacity:0; transform:translateY(28px) scale(0.97); }
    to   { opacity:1; transform:translateY(0)    scale(1);    }
}
@keyframes slideInRight {
    from { opacity:0; transform:translateX(30px); }
    to   { opacity:1; transform:translateX(0);    }
}
@keyframes slideInLeft {
    from { opacity:0; transform:translateX(-30px); }
    to   { opacity:1; transform:translateX(0);     }
}
@keyframes glowPulse {
    0%,100% { box-shadow: 0 4px 20px rgba(99,102,241,0.45); }
    50%      { box-shadow: 0 4px 32px rgba(139,92,246,0.72); }
}

.login-card {
    max-width: 440px;
    margin: 48px auto 0;
    padding: 48px 44px 40px;
    background: linear-gradient(155deg, rgba(30,41,59,0.65) 0%, rgba(15,23,42,0.85) 100%);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border-radius: 24px;
    border: 1px solid rgba(139,92,246,0.22);
    box-shadow: 0 32px 80px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.07);
    animation: fadeInUp 0.75s cubic-bezier(0.22,1,0.36,1) both;
    text-align: center;
}
.login-card h1 {
    font-family: 'Outfit', sans-serif !important;
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(95deg, #c084fc 10%, #818cf8 55%, #60a5fa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 8px 0;
    line-height: 1.2;
}
.login-card p.sub {
    color: #64748b;
    font-size: 13px;
    letter-spacing: 0.04em;
    margin: 0 0 36px 0;
    text-transform: uppercase;
    font-weight: 500;
}
.login-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 0 0 28px 0;
}

[data-testid="stTextInput"] label,
[data-testid="stTextInput"] > div > label {
    color: #64748b !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
[data-testid="stTextInput"] input {
    background: rgba(8,13,26,0.9) !important;
    color: #f1f5f9 !important;
    border: 1.5px solid #1e293b !important;
    border-radius: 12px !important;
    padding: 13px 16px !important;
    font-size: 14.5px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.22s ease, box-shadow 0.22s ease, background 0.22s ease !important;
    caret-color: #8b5cf6 !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #8b5cf6 !important;
    background: rgba(20,28,48,0.98) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.22) !important;
    outline: none !important;
}
[data-testid="stTextInput"] input::placeholder { color: #2d3a52 !important; }

[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 24px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    width: 100% !important;
    letter-spacing: 0.04em !important;
    cursor: pointer !important;
    transition: transform 0.22s ease, box-shadow 0.22s ease !important;
    animation: glowPulse 3s ease-in-out infinite !important;
    margin-top: 8px !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 36px rgba(99,102,241,0.7) !important;
}
[data-testid="stFormSubmitButton"] > button:active { transform: translateY(0) !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #060c18 0%, #0f0e2e 100%) !important;
    border-right: 1px solid rgba(139,92,246,0.1) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    background: rgba(15,23,42,0.9) !important;
    border-color: #1e293b !important;
    color: #94a3b8 !important;
    font-size: 13px !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.22s ease !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.55) !important;
}

.profile-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.88));
    border: 1px solid rgba(99,102,241,0.18);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 18px;
    transition: transform 0.22s ease, box-shadow 0.22s ease;
    box-shadow: 0 4px 18px rgba(0,0,0,0.4);
}
.profile-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(99,102,241,0.22);
}

.block-container { padding-top: 1.5rem !important; }

.chat-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    background: linear-gradient(95deg, #c084fc, #818cf8, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 2px 0;
    line-height: 1.25;
}
.chat-meta {
    font-size: 12px;
    color: #334155;
    margin: 0 0 28px 0;
    letter-spacing: 0.03em;
}

[data-testid="stChatMessage"] {
    border-radius: 18px !important;
    margin-bottom: 12px !important;
    padding: 14px 20px !important;
    border: none !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}
[data-testid="stChatMessage"]:hover { transform: scale(1.007) !important; }

[data-testid="stChatMessageUser"] {
    background: linear-gradient(135deg, #2d2b7a 0%, #3730a3 50%, #4338ca 100%) !important;
    border: 1px solid rgba(139,92,246,0.3) !important;
    box-shadow: 0 6px 24px rgba(67,56,202,0.4) !important;
    animation: slideInRight 0.42s cubic-bezier(0.22,1,0.36,1) both !important;
}
[data-testid="stChatMessageAssistant"] {
    background: rgba(15,23,42,0.75) !important;
    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    box-shadow: 0 6px 24px rgba(0,0,0,0.35) !important;
    animation: slideInLeft 0.42s cubic-bezier(0.22,1,0.36,1) both !important;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    border-radius: 50% !important;
    border: 1.5px solid rgba(139,92,246,0.35) !important;
}

[data-testid="stChatInput"],
.stChatInputContainer {
    background: rgba(6,12,24,0.92) !important;
    backdrop-filter: blur(22px) !important;
    -webkit-backdrop-filter: blur(22px) !important;
    border-top: 1px solid rgba(139,92,246,0.18) !important;
    padding: 14px 22px !important;
    box-shadow: 0 -12px 48px rgba(0,0,0,0.55) !important;
}
[data-testid="stChatInput"] textarea,
.stChatInputContainer textarea {
    background: rgba(15,23,42,0.95) !important;
    color: #f1f5f9 !important;
    border: 1.5px solid #1e293b !important;
    border-radius: 14px !important;
    font-size: 14px !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.22s ease, box-shadow 0.22s ease !important;
    caret-color: #8b5cf6 !important;
    padding: 12px 16px !important;
}
[data-testid="stChatInput"] textarea:focus,
.stChatInputContainer textarea:focus {
    border-color: #8b5cf6 !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.2) !important;
    outline: none !important;
}
[data-testid="stChatInput"] textarea::placeholder,
.stChatInputContainer textarea::placeholder { color: #1e293b !important; }

[data-testid="stChatInputSubmitButton"] button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border-radius: 10px !important;
    border: none !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stChatInputSubmitButton"] button:hover {
    transform: scale(1.1) !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.55) !important;
}

[data-testid="stAlertContainer"] {
    border-radius: 12px !important;
    margin-top: 14px !important;
    border: none !important;
}

hr { border-color: rgba(255,255,255,0.05) !important; margin: 16px 0 !important; }
</style>
""", unsafe_allow_html=True)
