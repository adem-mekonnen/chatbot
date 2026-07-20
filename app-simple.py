import streamlit as st
import requests
import uuid
import os
import time

# --- 1. CONFIGURATION ---
# In Render/Docker, the UI and API talk to each other on localhost:8000
BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Enterprise AI Agent",
    page_icon="🤖",
    layout="centered"
)

# Custom CSS for a professional enterprise look
st.markdown("""
<style>
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; border: 1px solid #e0e0e0; }
    .stButton > button { border-radius: 8px; font-weight: 600; }
    .main { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"

# --- 3. LOGIN INTERFACE ---
def login_ui():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/2597/2597388.png", width=80)
        st.title("Enterprise Login")
        st.markdown("Enter your credentials to access the secure AI Agent.")
        
        with st.form("login_form"):
            username = st.text_input("Username (Employee ID)")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")
            
            if submitted:
                try:
                    res = requests.post(f"{BACKEND_URL}/token", json={"username": username, "password": password})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.role = data.get("role", "user")
                        st.session_state.username = username
                        st.session_state.authenticated = True
                        st.success("Login Successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials. Please try again.")
                except Exception as e:
                    st.error(f"⚠️ Connection Error: Unable to reach the Brain (API).")

# --- 4. CHAT INTERFACE ---
def chat_ui():
    # Sidebar
    with st.sidebar:
        st.title("Agent Settings")
        st.success(f"User: {st.session_state.username}")
        st.info(f"Role: {st.session_state.role.capitalize()}")
        
        if st.button("🧹 Clear Chat"):
            st.session_state.messages = []
            st.rerun()
            
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.token = None
            st.rerun()
        
        st.divider()
        st.markdown("### Knowledge Base")
        st.caption("Connected to 27 Company Documents (PDF/TXT)")

    st.title("🤖 Enterprise Assistant")
    st.markdown("Ask me anything about company policy, benefits, or general tasks.")

    # Display History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("Message the Agent..."):
        # Display User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI Response from Backend
        with st.chat_message("assistant"):
            with st.spinner("Analyzing Knowledge Base..."):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                payload = {
                    "message": prompt,
                    "session_id": st.session_state.session_id
                }
                
                try:
                    response = requests.post(f"{BACKEND_URL}/chat", json=payload, headers=headers)
                    if response.status_code == 200:
                        answer = response.json()["response"]
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                    else:
                        st.error("AI service returned an error. Check logs.")
                except Exception as e:
                    st.error(f"Brain connection lost: {e}")

# --- 5. MAIN LOGIC ---
if not st.session_state.authenticated:
    login_ui()
else:
    chat_ui()