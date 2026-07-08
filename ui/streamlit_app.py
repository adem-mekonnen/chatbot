# ui/streamlit_app.py
import streamlit as st
import httpx
import jwt
import logging
import os
import uuid
import base64
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("enterprise-agent")

# ─────────────────────────────────────────────────────────────────────────────
# Backend URL
# Uses a dedicated API_BASE_URL env var.  DATABASE_URL is a SQLAlchemy
# connection string and must never be used as an HTTP endpoint.
# ─────────────────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="ABC Inc. Assistant",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & Base ────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    background-color: #080a12 !important;
    color: #e2e4ef !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton { display: none !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ── Animated Mesh Background ───────────────────────────────────────────── */
@keyframes meshShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.stApp {
    background:
        radial-gradient(ellipse at 20% 20%, rgba(79,70,229,0.12) 0%, transparent 55%),
        radial-gradient(ellipse at 80% 80%, rgba(109,40,217,0.10) 0%, transparent 55%),
        radial-gradient(ellipse at 60% 10%, rgba(59,130,246,0.07) 0%, transparent 50%),
        #080a12 !important;
    background-size: 200% 200% !important;
    animation: meshShift 18s ease infinite !important;
}

/* ── Block container padding ────────────────────────────────────────────── */
.main .block-container {
    padding: 0 2rem 120px 2rem !important;
    max-width: 960px !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d0f1a; }
::-webkit-scrollbar-thumb { background: #2a2e45; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #4f46e5; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════════════════
   LOGIN PAGE
══════════════════════════════════════════════════════════════════════════ */
@keyframes cardReveal {
    from { opacity: 0; transform: translateY(24px) scale(0.98); }
    to   { opacity: 1; transform: translateY(0)   scale(1);    }
}
@keyframes borderPulse {
    0%, 100% { box-shadow: 0 0 0 0   rgba(109,40,217,0), 0 24px 60px rgba(0,0,0,0.6); }
    50%       { box-shadow: 0 0 0 6px rgba(109,40,217,0.12), 0 24px 60px rgba(0,0,0,0.6); }
}

.login-wrap {
    min-height: 92vh;
    display: flex;
    align-items: center;
    justify-content: center;
}
.login-card {
    width: 100%;
    max-width: 440px;
    background: rgba(14,16,28,0.82);
    backdrop-filter: blur(24px) saturate(160%);
    -webkit-backdrop-filter: blur(24px) saturate(160%);
    border: 1px solid rgba(99,112,180,0.2);
    border-radius: 20px;
    padding: 44px 40px 36px;
    animation: cardReveal 0.5s cubic-bezier(0.22,0.61,0.36,1) both,
               borderPulse 4s ease 0.6s infinite;
}
.login-logo {
    display: flex;
    justify-content: center;
    margin-bottom: 22px;
}
.login-logo img {
    max-width: 120px;
    height: auto;
    filter: drop-shadow(0 0 18px rgba(109,40,217,0.35));
}
.login-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #ffffff;
    text-align: center;
    letter-spacing: -0.4px;
    margin: 0 0 6px;
}
.login-subtitle {
    font-size: 13px;
    color: #6b7080;
    text-align: center;
    margin: 0 0 28px;
    line-height: 1.5;
}
.login-divider {
    border: none;
    border-top: 1px solid rgba(99,112,180,0.15);
    margin: 20px 0;
}
.trust-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 12px;
    color: #4a5068;
    margin-top: 16px;
}
.trust-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 6px rgba(34,197,94,0.6);
    flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ── Login inputs ────────────────────────────────────────────────────────── */
.stTextInput label {
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.6px !important;
    text-transform: uppercase !important;
    color: #6b7280 !important;
    margin-bottom: 4px !important;
}
.stTextInput input {
    background-color: #0f1221 !important;
    border: 1px solid #1e2540 !important;
    border-radius: 10px !important;
    color: #e2e4ef !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput input:focus {
    border-color: #6d28d9 !important;
    box-shadow: 0 0 0 3px rgba(109,40,217,0.28), 0 0 14px rgba(79,70,229,0.2) !important;
    outline: none !important;
}
.stTextInput input::placeholder { color: #2e364d !important; }

/* ── Login submit button ─────────────────────────────────────────────────── */
.stForm [data-testid="stFormSubmitButton"] button {
    width: 100% !important;
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    padding: 13px 0 !important;
    margin-top: 4px !important;
    transition: opacity 0.2s ease, transform 0.15s ease,
                box-shadow 0.2s ease !important;
    box-shadow: 0 4px 20px rgba(109,40,217,0.35) !important;
}
.stForm [data-testid="stFormSubmitButton"] button:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 28px rgba(109,40,217,0.5) !important;
}
.stForm [data-testid="stFormSubmitButton"] button:active {
    transform: translateY(0) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0c18 0%, #0d0f1e 100%) !important;
    border-right: 1px solid rgba(79,70,229,0.15) !important;
    min-width: 240px !important;
    max-width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 20px 18px 24px !important;
}

/* ── Logo bar ────────────────────────────────────────────────────────────── */
.sidebar-logo-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0 18px;
    border-bottom: 1px solid rgba(79,70,229,0.14);
    margin-bottom: 18px;
}
.sidebar-logo-wrap img {
    width: 34px; height: 34px;
    object-fit: contain;
    border-radius: 8px;
    box-shadow: 0 0 12px rgba(109,40,217,0.3);
}
.sidebar-logo-wrap .s-brand {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.2px;
    line-height: 1.2;
}
.sidebar-logo-wrap .s-brand span {
    display: block;
    font-size: 10.5px;
    font-weight: 400;
    color: #3d4460;
    letter-spacing: 0.2px;
    margin-top: 1px;
}

/* ── Profile card ────────────────────────────────────────────────────────── */
.profile-card {
    background: rgba(79,70,229,0.07);
    border: 1px solid rgba(79,70,229,0.18);
    border-radius: 14px;
    padding: 14px 14px 12px;
    margin-bottom: 6px;
}
.profile-card .pc-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.profile-avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 700; color: #fff;
    flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(109,40,217,0.3), 0 4px 12px rgba(109,40,217,0.25);
}
.pc-name {
    font-size: 13.5px;
    font-weight: 600;
    color: #e2e4ef;
    line-height: 1.2;
}
.role-pill {
    display: inline-block;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 20px;
    background: rgba(79,70,229,0.2);
    color: #a5b4fc;
    border: 1px solid rgba(99,102,241,0.3);
    margin-top: 3px;
}
.session-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #3d4460;
    background: rgba(8,10,18,0.6);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 5px 9px;
    margin-top: 2px;
}
.session-badge .s-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 6px rgba(34,197,94,0.8);
    flex-shrink: 0;
    animation: pulse-dot 2.5s ease infinite;
}
@keyframes pulse-dot {
    0%,100% { box-shadow: 0 0 4px rgba(34,197,94,0.7); }
    50%      { box-shadow: 0 0 10px rgba(34,197,94,1); }
}

/* ── Section labels ──────────────────────────────────────────────────────── */
.sidebar-section-label {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #2a3050;
    margin: 20px 0 8px;
    padding-left: 1px;
}

/* ── Sidebar toggle ──────────────────────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stToggle"] {
    background: rgba(14,17,32,0.8) !important;
    border: 1px solid rgba(79,70,229,0.2) !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    margin-bottom: 10px !important;
}

/* ── Sidebar buttons ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] .stButton button {
    border-radius: 10px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.1px !important;
    transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    transform: translateY(-1px) !important;
}
/* New Conversation — subtle outline style */
[data-testid="stSidebar"] .stButton [kind="secondary"] button,
[data-testid="stSidebar"] .stButton button[kind="secondary"] {
    background: rgba(79,70,229,0.1) !important;
    border: 1px solid rgba(79,70,229,0.3) !important;
    color: #a5b4fc !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
    background: rgba(79,70,229,0.2) !important;
    border-color: rgba(99,102,241,0.5) !important;
    box-shadow: 0 4px 16px rgba(79,70,229,0.2) !important;
}
/* Sign Out — calm dark-red instead of bright red */
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: rgba(127,29,29,0.5) !important;
    border: 1px solid rgba(185,28,28,0.35) !important;
    color: #fca5a5 !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    background: rgba(153,27,27,0.65) !important;
    border-color: rgba(220,38,38,0.5) !important;
    box-shadow: 0 4px 16px rgba(185,28,28,0.25) !important;
}

/* ── Quick Links buttons inside expander ─────────────────────────────────── */
[data-testid="stSidebar"] .stExpander [data-testid="stVerticalBlock"] .stButton button {
    background: rgba(12,14,26,0.6) !important;
    border: 1px solid rgba(79,70,229,0.15) !important;
    color: #8b92b0 !important;
    font-size: 12px !important;
    padding: 8px 12px !important;
    margin-bottom: 6px !important;
    text-align: left !important;
}
[data-testid="stSidebar"] .stExpander [data-testid="stVerticalBlock"] .stButton button:hover {
    background: rgba(79,70,229,0.15) !important;
    border-color: rgba(109,40,217,0.35) !important;
    color: #c4c8e0 !important;
    box-shadow: 0 2px 12px rgba(79,70,229,0.18) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════════════════
   CHAT PAGE HEADER BAR
══════════════════════════════════════════════════════════════════════════ */
.chat-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 0 16px;
    border-bottom: 1px solid rgba(79,70,229,0.12);
    margin-bottom: 28px;
}
.chat-topbar-left { display: flex; align-items: center; gap: 14px; }

/* AI avatar ring */
.chat-avatar-lg {
    width: 46px; height: 46px;
    border-radius: 50%;
    background: linear-gradient(135deg, #312e81 0%, #6d28d9 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(109,40,217,0.35),
                0 0 20px rgba(109,40,217,0.3);
    position: relative;
}
/* Live pulse ring around avatar */
.chat-avatar-lg::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 1.5px solid rgba(109,40,217,0.4);
    animation: avatar-ring 2.8s ease infinite;
}
@keyframes avatar-ring {
    0%,100% { opacity: 0.5; transform: scale(1);    }
    50%      { opacity: 1;   transform: scale(1.08); }
}

.chat-topbar-title {
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.3px;
    margin: 0 0 2px;
    line-height: 1;
}
.chat-topbar-sub {
    font-size: 11.5px;
    color: #3d4460;
    margin: 0;
    letter-spacing: 0.1px;
}
.online-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    font-weight: 600;
    color: #4ade80;
    background: rgba(34,197,94,0.07);
    border: 1px solid rgba(34,197,94,0.18);
    border-radius: 20px;
    padding: 5px 12px;
    letter-spacing: 0.2px;
}
.online-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 7px rgba(34,197,94,0.9);
    animation: pulse-dot 2.5s ease infinite;
}

/* ══════════════════════════════════════════════════════════════════════════
   WELCOME / EMPTY STATE
══════════════════════════════════════════════════════════════════════════ */
.welcome-section {
    text-align: center;
    padding: 32px 16px 36px;
}
/* Gradient orb behind the icon */
.welcome-orb {
    width: 88px; height: 88px;
    margin: 0 auto 20px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%,
        rgba(99,102,241,0.35) 0%,
        rgba(109,40,217,0.18) 50%,
        transparent 75%);
    display: flex; align-items: center; justify-content: center;
    font-size: 40px;
    box-shadow: 0 0 40px rgba(109,40,217,0.2);
    border: 1px solid rgba(99,102,241,0.15);
}
.welcome-section h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 10px;
    letter-spacing: -0.4px;
}
.welcome-section p {
    font-size: 14px;
    color: #3d4460;
    margin: 0 0 32px;
    line-height: 1.7;
    max-width: 420px;
    margin-left: auto;
    margin-right: auto;
}
/* Label above the cards */
.qs-label {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    color: #2a3050;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ── Quick-start cards ───────────────────────────────────────────────────── */
[data-testid="stMain"] .stButton button {
    background: rgba(12,14,26,0.85) !important;
    border: 1px solid rgba(79,70,229,0.2) !important;
    border-radius: 16px !important;
    color: #9ba3c0 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 20px 16px !important;
    text-align: center !important;
    line-height: 1.6 !important;
    min-height: 100px !important;
    width: 100% !important;
    transition: border-color 0.22s ease, transform 0.18s ease,
                box-shadow 0.22s ease, background 0.22s ease,
                color 0.18s ease !important;
    backdrop-filter: blur(10px) !important;
    white-space: pre-wrap !important;
}
[data-testid="stMain"] .stButton button:hover {
    background: rgba(22,20,54,0.9) !important;
    border-color: rgba(109,40,217,0.55) !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 28px rgba(79,70,229,0.22),
                0 0 0 1px rgba(99,102,241,0.18) !important;
    color: #e2e4ef !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   CHAT BUBBLES
══════════════════════════════════════════════════════════════════════════ */
@keyframes bubbleIn {
    from { opacity: 0; transform: translateY(14px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0)    scale(1);    }
}

.stChatMessage {
    border-radius: 20px !important;
    padding: 16px 20px !important;
    margin-bottom: 12px !important;
    max-width: 76% !important;
    animation: bubbleIn 0.32s cubic-bezier(0.22,0.61,0.36,1) both !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    border: none !important;
    background: transparent !important;
}
.stChatMessage:hover { transform: scale(1.006) !important; }

/* Assistant — frosted glass */
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: rgba(14,17,34,0.78) !important;
    backdrop-filter: blur(18px) saturate(170%) !important;
    -webkit-backdrop-filter: blur(18px) saturate(170%) !important;
    border: 1px solid rgba(79,70,229,0.15) !important;
    box-shadow: 0 4px 32px rgba(0,0,0,0.5),
                inset 0 1px 0 rgba(255,255,255,0.04) !important;
    margin-left: 0 !important;
    margin-right: auto !important;
}
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]):hover {
    box-shadow: 0 6px 40px rgba(0,0,0,0.6),
                0 0 0 1px rgba(79,70,229,0.22),
                inset 0 1px 0 rgba(255,255,255,0.055) !important;
}

/* User — indigo/purple gradient */
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, #3730a3 0%, #5b21b6 50%, #6d28d9 100%) !important;
    border: 1px solid rgba(139,92,246,0.28) !important;
    box-shadow: 0 4px 24px rgba(79,70,229,0.38),
                inset 0 1px 0 rgba(255,255,255,0.1) !important;
    margin-left: auto !important;
    margin-right: 0 !important;
}
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]):hover {
    box-shadow: 0 6px 32px rgba(109,40,217,0.52),
                0 0 0 1px rgba(139,92,246,0.4),
                inset 0 1px 0 rgba(255,255,255,0.12) !important;
}
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
.stChatMessage[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown {
    color: #f0f0ff !important;
}

/* Avatar icons inside bubbles */
[data-testid="chatAvatarIcon-assistant"],
[data-testid="chatAvatarIcon-user"] {
    border-radius: 50% !important;
}
[data-testid="chatAvatarIcon-user"] {
    background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
    box-shadow: 0 0 10px rgba(109,40,217,0.4) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════════════════
   FLOATING CHAT INPUT BAR
══════════════════════════════════════════════════════════════════════════ */
.stChatInputContainer {
    position: fixed !important;
    bottom: 22px !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: clamp(320px, 56vw, 820px) !important;
    background: rgba(8,10,22,0.88) !important;
    backdrop-filter: blur(28px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(28px) saturate(200%) !important;
    border: 1px solid rgba(79,70,229,0.22) !important;
    border-radius: 26px !important;
    box-shadow: 0 8px 48px rgba(0,0,0,0.65),
                0 0 0 1px rgba(255,255,255,0.03) inset !important;
    padding: 8px 12px !important;
    z-index: 999 !important;
    transition: border-color 0.22s ease, box-shadow 0.22s ease !important;
}
.stChatInputContainer:focus-within {
    border-color: rgba(109,40,217,0.55) !important;
    box-shadow: 0 8px 48px rgba(0,0,0,0.7),
                0 0 0 3px rgba(109,40,217,0.16),
                0 0 0 1px rgba(255,255,255,0.04) inset !important;
}
.stChatInputContainer textarea {
    background: transparent !important;
    border: none !important;
    color: #e2e4ef !important;
    font-size: 14.5px !important;
    line-height: 1.55 !important;
    resize: none !important;
    font-family: 'Inter', sans-serif !important;
}
.stChatInputContainer textarea::placeholder { color: #252d48 !important; }
.stChatInputContainer button {
    background: linear-gradient(135deg, #4f46e5 0%, #6d28d9 100%) !important;
    border-radius: 16px !important;
    border: none !important;
    box-shadow: 0 2px 12px rgba(109,40,217,0.45) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stChatInputContainer button:hover {
    transform: scale(1.08) !important;
    box-shadow: 0 4px 20px rgba(109,40,217,0.6) !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   ACCESSIBILITY & RESPONSIVE ENHANCEMENTS
══════════════════════════════════════════════════════════════════════════ */

/* Focus management for keyboard users */
*:focus-visible {
    outline: 2px solid #6d28d9 !important;
    outline-offset: 2px !important;
}

/* Skip to content link for screen readers */
.skip-link {
    position: absolute;
    top: -40px;
    left: 6px;
    background: #4f46e5;
    color: white;
    padding: 8px;
    text-decoration: none;
    z-index: 1000;
    border-radius: 4px;
}
.skip-link:focus { top: 6px; }

/* Improve contrast for accessibility */
.login-subtitle { color: #8b8ba8 !important; }
.chat-topbar-sub { color: #5a5b73 !important; }

/* Mobile responsiveness */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem !important;
        max-width: 100% !important;
    }
    
    .login-card {
        margin: 20px auto !important;
        padding: 32px 24px !important;
        max-width: 90% !important;
    }
    
    .chat-topbar {
        flex-direction: column !important;
        gap: 12px !important;
    }
    
    .chat-avatar-lg {
        width: 40px !important;
        height: 40px !important;
        font-size: 18px !important;
    }
    
    .stChatInputContainer {
        width: calc(100vw - 2rem) !important;
        left: 1rem !important;
        transform: none !important;
    }
}

/* Print styles */
@media print {
    .stSidebar, .stChatInputContainer, .online-badge { display: none !important; }
    .stChatMessage { box-shadow: none !important; border: 1px solid #ccc !important; }
}

/* Reduced motion for accessibility */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* High contrast mode support */
@media (prefers-contrast: high) {
    .stApp { background: #000 !important; color: #fff !important; }
    .login-card { border: 2px solid #fff !important; }
    .stChatMessage { border: 1px solid #fff !important; }
}

/* Loading indicator improvements */
.stSpinner > div {
    border-color: #6d28d9 transparent transparent transparent !important;
}

/* ── Main content top padding & bottom breathing room ────────────────────── */
.main .block-container {
    padding-top: 10px !important;
    padding-bottom: 115px !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 980px !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
for _k, _v in {
    "access_token": None,
    "refresh_token": None,
    "user_id": None,
    "role": None,
    "session_id": str(uuid.uuid4())[:8],
    "messages": [],
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — load logo as base64
# ─────────────────────────────────────────────────────────────────────────────
def _logo_b64() -> str | None:
    p = Path(__file__).parent / "abc_corporate_logo.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else None

_LOGO = _logo_b64()
_LOGO_TAG = (
    f'<img src="data:image/png;base64,{_LOGO}" alt="ABC Inc." />'
    if _LOGO else '<span style="font-size:40px;">🏢</span>'
)

# ─────────────────────────────────────────────────────────────────────────────
# SCREEN ROUTER
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.access_token:
    # ══════════════════════════════════════════════════════════════════════════
    # LOGIN SCREEN
    # ══════════════════════════════════════════════════════════════════════════
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown(f"""
        <div class="login-card">
            <div class="login-logo">{_LOGO_TAG}</div>
            <p class="login-title">ABC Inc. Portal</p>
            <p class="login-subtitle">Secure Corporate AI&nbsp;Assistant&nbsp;Gateway<br>
               Sign in with your employee credentials to continue.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("secure_login_form", clear_on_submit=False):
            username_input = st.text_input("User ID / Employee ID", placeholder="Enter your employee ID")
            password_input = st.text_input("Security Password", placeholder="Enter your password", type="password")
            st.write("")
            submit_button = st.form_submit_button("Sign In  →", use_container_width=True)

            if submit_button and username_input and password_input:
                with st.spinner("🔐 Verifying credentials…"):
                    try:
                        with httpx.Client(timeout=30.0) as client:
                            res = client.post(
                                f"{BACKEND_URL}/token",
                                json={"username": username_input, "password": password_input},
                            )
                            if res.status_code == 200:
                                data = res.json()
                                access_token  = data.get("access_token")
                                refresh_token = data.get("refresh_token")
                                # Decode WITHOUT signature verification — display purposes only.
                                # The server validates the signature on every /chat request;
                                # we only read user_id and role here to populate the UI.
                                # An attacker who tampers with the payload will still be
                                # rejected by the backend on the first API call.
                                payload = jwt.decode(
                                    access_token,
                                    options={"verify_signature": False},
                                    algorithms=["HS256"],
                                )
                                st.session_state.access_token  = access_token
                                st.session_state.refresh_token = refresh_token
                                st.session_state.user_id       = payload.get("user_id") or payload.get("sub")
                                st.session_state.role          = payload.get("role", "customer")
                                st.success("Authorized — loading workspace…")
                                st.rerun()
                            else:
                                st.error("Access Denied: Invalid User ID or password.")
                    except httpx.TimeoutException:
                        st.error("Request timed out. Ensure the FastAPI backend is running.")
                    except Exception:
                        st.error("Service Unavailable: Ensure the FastAPI backend is running.")

        st.markdown("""
        <hr class="login-divider">
        <div class="trust-badge">
            <span class="trust-dot"></span>
            256-bit TLS encrypted &nbsp;·&nbsp; JWT-secured session
        </div>
        """, unsafe_allow_html=True)

else:
    # ══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATED WORKSPACE
    # ══════════════════════════════════════════════════════════════════════════

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        # Brand bar
        small_logo = (
            f'<img src="data:image/png;base64,{_LOGO}" alt="ABC Inc." />'
            if _LOGO else "🏢"
        )
        st.markdown(f"""
        <div class="sidebar-logo-wrap">
            {small_logo}
            <div class="s-brand">ABC Inc.<span>Enterprise AI Assistant</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Profile card
        initials = str(st.session_state.user_id)[:2].upper()
        role_label = str(st.session_state.role or "user").upper()
        st.markdown(f"""
        <div class="profile-card">
            <div class="pc-header">
                <div class="profile-avatar" aria-label="User avatar">{initials}</div>
                <div>
                    <div class="pc-name">Employee {st.session_state.user_id}</div>
                    <div class="role-pill" role="status" aria-label="User role">{role_label}</div>
                </div>
            </div>
            <div class="session-badge" role="status">
                <span class="s-dot" aria-hidden="true"></span>
                Session&nbsp;<strong style="color:#6b7280">{st.session_state.session_id}</strong>
                &nbsp;·&nbsp;Active
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Controls section
        st.markdown('<div class="sidebar-section-label">Controls</div>', unsafe_allow_html=True)
        # NOTE: The compliance gate is enforced server-side based on the user's role.
        # Admin users automatically receive general-knowledge fallback access;
        # all other roles are held to strict RAG-only mode regardless of UI state.
        _is_admin = str(st.session_state.role or "").lower() == "admin"
        st.caption(
            "🔓 Compliance gate: **relaxed** (admin mode)"
            if _is_admin else
            "🔒 Compliance gate: **strict** (policy documents only)"
        )

        if st.button("＋  New Conversation", use_container_width=True, type="secondary", help="Start a fresh conversation (Ctrl+N)"):
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.messages   = []
            st.rerun()

        # Support section
        st.markdown('<div class="sidebar-section-label">Support</div>', unsafe_allow_html=True)
        st.caption("IT Helpdesk: helpdesk@globalcorp.com")
        
        # Quick access links - now clickable and functional
        with st.expander("📚 Quick Links", expanded=False):
            if st.button("📖 Employee Handbook", use_container_width=True, key="link_handbook"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Tell me about the employee handbook and what information it contains",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()
            
            if st.button("💻 IT Support Portal", use_container_width=True, key="link_it"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What IT policies and computer usage guidelines should I follow?",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()
            
            if st.button("🏥 Benefits Portal", use_container_width=True, key="link_benefits"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "What employee benefits and perks does the company offer?",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()
            
            if st.button("🎓 Learning & Development", use_container_width=True, key="link_learning"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Tell me about career development and training opportunities",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()

        st.write("")
        if st.button("Sign Out", use_container_width=True, type="primary", help="Sign out securely"):
            if st.session_state.refresh_token:
                try:
                    with httpx.Client(timeout=10.0) as client:
                        client.post(
                            f"{BACKEND_URL}/logout",
                            json={"refresh_token": st.session_state.refresh_token},
                        )
                except httpx.TimeoutException:
                    logger.warning("Logout request timed out — token may still be active server-side.")
                except Exception as exc:
                    logger.warning("Logout request failed: %s", exc)
            for k in ("access_token", "refresh_token", "user_id", "role", "messages"):
                st.session_state[k] = None if k != "messages" else []
            st.rerun()

    # ── Chat top bar ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="chat-topbar">
        <div class="chat-topbar-left">
            <div class="chat-avatar-lg">🤖</div>
            <div>
                <p class="chat-topbar-title">ABC AI Assistant</p>
                <p class="chat-topbar-sub">Policy & HR Knowledge Base · Secure Ledger V2</p>
            </div>
        </div>
        <div class="online-badge">
            <span class="online-dot"></span> Online
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Welcome / empty state ─────────────────────────────────────────────────
    if not st.session_state.messages:
        st.markdown(f"""
        <div class="welcome-section">
            <div class="welcome-orb">✨</div>
            <h2>Welcome back, Employee {st.session_state.user_id}</h2>
            <p>Ask me anything about company policies, benefits,<br>
               leave, payroll, or your account balance.</p>
            <div class="qs-label">Quick Start</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            if st.button(
                "📅  Leave & PTO\n\nHow many vacation days\ndo I earn per year?",
                use_container_width=True,
            ):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "How many vacation days do I earn per year, and is there a cap on how many I can carry over?",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()
        with c2:
            if st.button(
                "💰  401(k) & Benefits\n\nDoes the company match\nmy 401k contributions?",
                use_container_width=True,
            ):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Does the company match my 401k contributions, and what is the vesting schedule for the company match?",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()
        with c3:
            if st.button(
                "🏦  Account Ledger\n\nWhat is my current\naccount balance?",
                use_container_width=True,
            ):
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"balance of {st.session_state.user_id}",
                    "time": datetime.now().strftime("%H:%M"),
                })
                st.rerun()

    # ── Chat history ──────────────────────────────────────────────────────────
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("time"):
                st.markdown(f'<span class="msg-time">{m["time"]}</span>', unsafe_allow_html=True)

    # ── Processing loop ───────────────────────────────────────────────────────
    prompt = None

    # Quick-start card click: auto-fire last user message if it's the only one
    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and len(st.session_state.messages) == 1
    ):
        prompt = st.session_state.messages[-1]["content"]
    else:
        prompt = st.chat_input("Ask about policies, benefits, leave, payroll…")

    if prompt:
        now = datetime.now().strftime("%H:%M")
        if not st.session_state.messages or st.session_state.messages[-1]["content"] != prompt:
            st.session_state.messages.append({"role": "user", "content": prompt, "time": now})
            with st.chat_message("user"):
                st.write(prompt)
                st.markdown(f'<span class="msg-time">{now}</span>', unsafe_allow_html=True)

        bot_reply = ""

        def _post_chat(client: httpx.Client, token: str) -> httpx.Response:
            """POST /chat with the current access token. Does not raise on 4xx/5xx."""
            return client.post(
                f"{BACKEND_URL}/chat",
                json={
                    "message":    prompt,
                    "session_id": st.session_state.session_id,
                    # bypass_rag_gate removed — gate is resolved server-side from the user's role.
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        def _try_refresh(client: httpx.Client) -> bool:
            """
            Performs Refresh Token Rotation.  Updates session tokens in place.
            Returns True if the refresh succeeded, False otherwise.
            """
            if not st.session_state.refresh_token:
                return False
            try:
                ref = client.post(
                    f"{BACKEND_URL}/refresh",
                    json={"refresh_token": st.session_state.refresh_token},
                )
                if ref.status_code == 200:
                    ref_data = ref.json()
                    st.session_state.access_token  = ref_data.get("access_token")
                    st.session_state.refresh_token = ref_data.get("refresh_token")
                    return True
            except Exception as exc:
                logger.warning("Token refresh failed: %s", exc)
            return False

        with st.spinner("🤖 Processing your request…"):
            try:
                with httpx.Client(timeout=60.0) as client:  # Increased timeout for LLM processing
                    response = _post_chat(client, st.session_state.access_token)

                    if response.status_code == 200:
                        bot_reply = response.json().get("response", "")

                    elif response.status_code == 401:
                        # Access token expired — attempt RTR and retry once.
                        if _try_refresh(client):
                            retry = _post_chat(client, st.session_state.access_token)
                            if retry.status_code == 200:
                                bot_reply = retry.json().get("response", "")
                            else:
                                bot_reply = "🔒 Session expired. Please sign out and re-authenticate."
                        else:
                            bot_reply = "🔒 Session expired. Please sign out and re-authenticate."

                    elif response.status_code == 429:
                        bot_reply = "🚦 Too many requests. Please wait a moment before trying again."
                    elif response.status_code >= 500:
                        bot_reply = "🚨 Server error. Our team has been notified. Please try again later."
                    else:
                        bot_reply = f"⚠️ Unexpected error (status {response.status_code}). Please try again."

            except httpx.TimeoutException:
                bot_reply = (
                    "⏱️ Request timed out after 60 seconds. The AI model may be processing a complex query. "
                    "Please try a simpler question or try again later."
                )
            except httpx.NetworkError as exc:
                logger.warning("Network error during chat request: %s", exc)
                bot_reply = "🌐 Network error: Could not reach the API service. Please check your connection."
            except Exception as exc:
                logger.exception("Unexpected error during chat request: %s", exc)
                bot_reply = "💥 An unexpected error occurred. Please refresh the page and try again."

        reply_time = datetime.now().strftime("%H:%M")
        with st.chat_message("assistant"):
            st.write(bot_reply)
            st.markdown(f'<span class="msg-time">{reply_time}</span>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply, "time": reply_time})
        st.rerun()
