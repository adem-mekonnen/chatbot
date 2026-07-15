"""
Simplified Streamlit app for deployment testing
This version works without RAG/ML dependencies
"""
import streamlit as st
import os
import sys
import logging

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./enterprise_state.db")
os.environ.setdefault("USE_HUGGINGFACE_FALLBACK", "true")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enterprise-agent-simple")

st.set_page_config(
    page_title="Enterprise AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
    }
    .stTextInput > div > div > input {
        background-color: #2d3748;
        color: white;
        border-radius: 10px;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        padding: 0.75rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🤖 Enterprise AI Agent")
st.markdown("### Secure Authentication & Chat System")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Demo users (hardcoded for simple deployment)
DEMO_USERS = {
    "alice": {"password": "alice123", "role": "customer", "balance": 12345.67},
    "bob": {"password": "bob123", "role": "customer", "balance": 9876.54},
    "admin": {"password": "admin123", "role": "admin", "balance": 25000.00}
}

def authenticate(username, password):
    """Simple authentication"""
    # Strip whitespace from inputs
    username = username.strip() if username else ""
    password = password.strip() if password else ""
    
    user = DEMO_USERS.get(username)
    if user and user["password"] == password:
        return True, user["role"]
    return False, None

def get_balance(username):
    """Get user balance"""
    return DEMO_USERS.get(username, {}).get("balance", 0)

def simple_chat_response(message, username, role):
    """Simple chat response without LLM"""
    message_lower = message.lower()
    
    # Balance queries
    if "balance" in message_lower:
        if role == "admin" and any(user in message_lower for user in ["alice", "bob"]):
            # Admin cross-user query
            for user in ["alice", "bob"]:
                if user in message_lower:
                    balance = get_balance(user)
                    return f"✅ Admin Access: {user.capitalize()}'s account balance is ${balance:,.2f}"
        else:
            # Own balance
            balance = get_balance(username)
            return f"Your account balance is ${balance:,.2f}"
    
    # Policy questions (mock responses)
    elif "vacation" in message_lower or "time off" in message_lower:
        return "📖 Vacation Policy: Employees receive 15 days of paid vacation per year. Vacation must be requested at least 2 weeks in advance through the HR portal."
    
    elif "benefit" in message_lower:
        return "💼 Benefits: We offer comprehensive health insurance, 401(k) matching up to 5%, dental and vision coverage, and flexible work arrangements."
    
    elif "work from home" in message_lower or "wfh" in message_lower or "remote" in message_lower:
        return "🏠 Remote Work Policy: Employees can work from home up to 3 days per week. Please coordinate with your manager and update your calendar."
    
    elif "hello" in message_lower or "hi" in message_lower:
        return f"Hello {username}! 👋 I'm your Enterprise AI Assistant. I can help you with account balances, company policies, and benefits information."
    
    else:
        return f"I understand you're asking about: '{message}'. This is a simplified deployment version. For full AI-powered responses, the complete system needs ML dependencies. Currently I can help with:\n\n✅ Account balances\n✅ Vacation policies\n✅ Benefits information\n✅ Remote work policies\n\nTry asking: 'What is my balance?' or 'Tell me about vacation policy'"

# Main app logic
if not st.session_state.authenticated:
    # Login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Login")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if username and password:
                    # Strip whitespace
                    username = username.strip()
                    password = password.strip()
                    
                    authenticated, role = authenticate(username, password)
                    if authenticated:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.success(f"✅ Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                        st.info(f"💡 Tip: Make sure you're typing exactly: username='{username}' (Check for typos!)")
                else:
                    st.warning("⚠️ Please enter both username and password")
        
        # Demo credentials
        with st.expander("🎓 Demo Credentials"):
            st.markdown("""
            **Customer Accounts:**
            - Username: `alice` | Password: `alice123`
            - Username: `bob` | Password: `bob123`
            
            **Administrator:**
            - Username: `admin` | Password: `admin123`
            """)

else:
    # Chat interface
    st.markdown(f"### Welcome, {st.session_state.username}! 👋")
    st.markdown(f"**Role:** {st.session_state.role.capitalize()}")
    
    # Logout button
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    
    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = simple_chat_response(
                    prompt, 
                    st.session_state.username, 
                    st.session_state.role
                )
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Quick actions
    st.markdown("### 💡 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💰 Check Balance"):
            msg = "What is my balance?"
            st.session_state.messages.append({"role": "user", "content": msg})
            response = simple_chat_response(msg, st.session_state.username, st.session_state.role)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col2:
        if st.button("🏖️ Vacation Policy"):
            msg = "What is the vacation policy?"
            st.session_state.messages.append({"role": "user", "content": msg})
            response = simple_chat_response(msg, st.session_state.username, st.session_state.role)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    with col3:
        if st.button("💼 Benefits"):
            msg = "Tell me about benefits"
            st.session_state.messages.append({"role": "user", "content": msg})
            response = simple_chat_response(msg, st.session_state.username, st.session_state.role)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: rgba(255,255,255,0.6); padding: 1rem;'>
    <p>🤖 Enterprise AI Agent - Simplified Deployment Version</p>
    <p style='font-size: 0.9em;'>This version works without heavy ML dependencies for easy deployment.</p>
</div>
""", unsafe_allow_html=True)
