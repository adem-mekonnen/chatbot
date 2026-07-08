# 🚀 Enterprise AI Agent - Quick Reference

## 🌐 Access URLs

- **Web UI**: http://localhost:8501 (Streamlit interface)
- **API Docs**: http://localhost:8000/docs (Interactive API documentation)
- **Health Check**: http://localhost:8000/health (System status)

## 🔐 Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Administrator |
| `alice` | `alice123` | Customer |
| `bob` | `bob123` | Customer |

## 🎮 Start/Stop Commands

### Start Services
```bash
# Terminal 1: Start Backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Start UI
streamlit run ui/streamlit_app.py --server.port 8501
```

### Stop Services
- Press `Ctrl+C` in each terminal

## 🧪 Testing Commands

```bash
# Quick login test
python scripts/test_login.py

# Full system verification
python scripts/final_verification.py

# Check deployment readiness
python scripts/check_deployment.py

# Run test suite
pytest tests/ -v
```

## 💬 Example Queries

### For Customers (alice/bob)
- "What is my account balance?"
- "What are the vacation policies?"
- "Tell me about company benefits"
- "What is the work from home policy?"
- "How do I request time off?"

### For Administrators (admin)
- "What is alice's balance?"
- "Show me bob's account information"
- All customer queries above also work

## 🔍 Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend not responding | Check if running: `curl http://localhost:8000/health` |
| UI not loading | Check if running: `curl http://localhost:8501` |
| Login fails | Run: `python scripts/test_login.py` |
| Ollama errors | Check: `curl http://localhost:11434/api/tags` |

## 📊 Current Status

✅ Backend: Running on port 8000  
✅ UI: Running on port 8501  
✅ Ollama: Running on port 11434  
✅ Tests: 11/11 passing (100%)  
✅ Status: **FULLY OPERATIONAL**

## 📁 Important Files

- **Configuration**: `.env`
- **Database**: `enterprise_state.db`
- **Vector Store**: `./vectorstore/`
- **Knowledge Base**: `./data/knowledge_base/`
- **Logs**: Check terminal output

## 🆘 Emergency Commands

```bash
# Reset admin password
python scripts/reset_admin.py

# List all accounts
python scripts/list_accounts.py

# Reinitialize database
python scripts/setup_demo_users.py

# Reingest knowledge base
python scripts/ingest.py
```

---

**For detailed information, see: DEPLOYMENT_COMPLETE.md**
