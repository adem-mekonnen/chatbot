# ✅ Free Deployment Checklist

Follow these steps to deploy your Enterprise AI Agent to a free hosting platform.

---

## 🎯 Quick Start (Choose Your Platform)

### Option A: Streamlit Cloud (Easiest - 5 minutes) ⭐ Recommended

- [ ] **Step 1**: Get HuggingFace Token
  - Go to https://huggingface.co/settings/tokens
  - Create new token (Read access)
  - Copy and save the token

- [ ] **Step 2**: Push to GitHub
  ```bash
  git init
  git add .
  git commit -m "Initial deployment"
  git remote add origin https://github.com/YOUR-USERNAME/enterprise-agent.git
  git push -u origin main
  ```

- [ ] **Step 3**: Deploy on Streamlit Cloud
  - Go to https://share.streamlit.io
  - Click "New app"
  - Connect GitHub and select your repository
  - Main file: `app.py`
  - Click "Advanced settings" → Add secrets:
    ```
    JWT_SECRET_KEY = "your-long-random-secret-key-min-32-chars"
    HF_INFERENCE_TOKEN = "your-huggingface-token"
    DATABASE_URL = "sqlite+aiosqlite:///./enterprise_state.db"
    CHROMA_PERSIST_DIR = "./vectorstore"
    USE_HUGGINGFACE_FALLBACK = "true"
    ```
  - Click "Deploy!"

- [ ] **Step 4**: Test Your App
  - Wait 2-3 minutes for deployment
  - Visit your app URL: `https://YOUR-APP.streamlit.app`
  - Login with: `alice` / `alice123`
  - Test chatbot functionality

---

### Option B: Render (Full Stack - 15 minutes)

- [ ] **Step 1**: Prerequisites
  - Get HuggingFace token (see Option A, Step 1)
  - Sign up at https://render.com (free)
  - Push code to GitHub (see Option A, Step 2)

- [ ] **Step 2**: Deploy Backend API
  - Go to Render Dashboard
  - Click "New +" → "Web Service"
  - Connect GitHub repository
  - Settings:
    - Name: `enterprise-agent-api`
    - Environment: `Python 3`
    - Build Command: `pip install -r requirements.txt && python scripts/ingest.py`
    - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Add Environment Variables:
    ```
    JWT_SECRET_KEY = (click "Generate")
    HF_INFERENCE_TOKEN = your-token
    DATABASE_URL = sqlite+aiosqlite:///./enterprise_state.db
    CHROMA_PERSIST_DIR = ./vectorstore
    USE_HUGGINGFACE_FALLBACK = true
    ```
  - Click "Create Web Service"

- [ ] **Step 3**: Deploy UI (Optional, or use Streamlit Cloud)
  - Click "New +" → "Web Service"  
  - Same repository
  - Settings:
    - Name: `enterprise-agent-ui`
    - Start Command: `streamlit run ui/streamlit_app.py --server.port $PORT`
    - Add Environment Variable:
      ```
      API_URL = https://your-api-url.onrender.com
      ```

- [ ] **Step 4**: Test Deployment
  - Visit API: `https://your-api-name.onrender.com/health`
  - Visit UI: `https://your-ui-name.onrender.com`
  - Test login and chat

---

### Option C: Railway (Alternative Full Stack - 15 minutes)

- [ ] **Step 1**: Prerequisites
  - Get HuggingFace token (see Option A, Step 1)
  - Sign up at https://railway.app (free)
  - Push code to GitHub (see Option A, Step 2)

- [ ] **Step 2**: Deploy Backend
  - Go to Railway Dashboard
  - Click "New Project" → "Deploy from GitHub repo"
  - Select your repository
  - Railway auto-detects Python
  - Click on service → "Variables" tab
  - Add environment variables:
    ```
    JWT_SECRET_KEY = your-secret-key
    HF_INFERENCE_TOKEN = your-huggingface-token
    DATABASE_URL = sqlite+aiosqlite:///./enterprise_state.db
    CHROMA_PERSIST_DIR = ./vectorstore
    USE_HUGGINGFACE_FALLBACK = true
    PORT = 8000
    ```
  - Click "Settings" → "Generate Domain"

- [ ] **Step 3**: Test Deployment
  - Visit: `https://your-app.railway.app/health`
  - Should return: `{"status":"ok",...}`

---

## 🔧 Pre-Deployment Configuration

### Files Created/Modified:

✅ **Configuration Files** (already created):
- [x] `.gitignore` - Excludes secrets and local files
- [x] `.streamlit/config.toml` - Streamlit configuration
- [x] `.streamlit/secrets.toml.example` - Example secrets file
- [x] `render.yaml` - Render deployment config
- [x] `railway.json` - Railway deployment config
- [x] `Procfile` - Process definition for hosting

### Before Deploying:

- [ ] Review `.env` file - ensure no hardcoded secrets
- [ ] Test locally: `streamlit run app.py`
- [ ] Verify all tests pass: `python scripts/final_verification.py`
- [ ] Commit all changes to git
- [ ] Push to GitHub

---

## 📝 Environment Variables Reference

### Required for All Platforms:

| Variable | Example Value | Where to Get |
|----------|---------------|--------------|
| `JWT_SECRET_KEY` | `your-random-32-char-string` | Generate random string |
| `HF_INFERENCE_TOKEN` | `hf_xxxxx` | https://huggingface.co/settings/tokens |
| `DATABASE_URL` | `sqlite+aiosqlite:///./enterprise_state.db` | Use this exact value |
| `CHROMA_PERSIST_DIR` | `./vectorstore` | Use this exact value |
| `USE_HUGGINGFACE_FALLBACK` | `true` | Set to `true` for cloud |

### Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_COLLECTION` | `enterprise_docs` | Vector store collection name |
| `OLLAMA_URL` | `http://localhost:11434` | Not used in cloud deployment |
| `OLLAMA_MODEL` | `llama3.2:latest` | Not used in cloud deployment |

---

## 🧪 Post-Deployment Testing

After deployment, verify functionality:

### 1. Health Check
```bash
curl https://your-app-url/health
# Expected: {"status":"ok","timestamp":"..."}
```

### 2. Web UI Test
- [ ] Open browser to your app URL
- [ ] Login page loads
- [ ] Can login with: `alice` / `alice123`
- [ ] Chat interface appears
- [ ] Can send a message
- [ ] Receives a response

### 3. Functionality Tests
- [ ] Test balance query: "What is my account balance?"
- [ ] Test policy query: "What are the vacation policies?"
- [ ] Test admin access (login as `admin` / `admin123`)
- [ ] Test cross-user query (admin only): "What is alice's balance?"

---

## 🚨 Common Issues & Solutions

### Issue: "Module not found" error
**Solution**: Ensure `requirements.txt` is complete and in the root directory

### Issue: App crashes on startup
**Solution**: Check environment variables are set correctly, especially `HF_INFERENCE_TOKEN`

### Issue: "Database locked" error
**Solution**: Using `aiosqlite` should prevent this. Verify `DATABASE_URL` includes `+aiosqlite`

### Issue: LLM timeout or no response
**Solution**: 
- Verify `USE_HUGGINGFACE_FALLBACK=true`
- Check HuggingFace token is valid
- HuggingFace free tier has rate limits - wait and retry

### Issue: Vector store/knowledge base not working
**Solution**: Ensure `scripts/ingest.py` runs during build (included in Render config)

### Issue: App sleeps after 15 minutes (free tier)
**Solution**: 
- This is normal for free tier
- First request after sleep takes 30-60 seconds
- Use uptime monitor: https://uptimerobot.com (keeps app awake)

---

## 📊 Platform Comparison

| Feature | Streamlit Cloud | Render | Railway |
|---------|----------------|--------|---------|
| Setup Time | 5 min | 15 min | 15 min |
| Free Tier | Unlimited | 750 hrs/mo | $5 credit/mo |
| Auto-deploy | ✅ | ✅ | ✅ |
| Custom Domain | ❌ | ✅ | ✅ |
| Backend + UI | UI only | Both | Both |
| Ease of Use | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎯 Recommended Path

1. **For Quick Demo**: Use **Streamlit Cloud** (easiest, fastest)
2. **For Learning**: Try **Render** (full-stack experience)
3. **For Production**: Start with **Railway** (better performance)

---

## 📞 Getting Help

- **Streamlit Docs**: https://docs.streamlit.io/streamlit-community-cloud
- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://docs.railway.app
- **HuggingFace**: https://huggingface.co/docs/api-inference

---

## ✅ Final Checklist

Before going live:

- [ ] HuggingFace API token obtained
- [ ] Code committed and pushed to GitHub
- [ ] Platform selected and account created
- [ ] Environment variables configured
- [ ] App deployed successfully
- [ ] Health endpoint responding
- [ ] Login functionality tested
- [ ] Chat functionality working
- [ ] Demo users can authenticate
- [ ] Knowledge base queries responding

---

**Ready to deploy? Pick your platform and follow the steps!** 🚀

**Need the detailed guide?** See `FREE_DEPLOYMENT_GUIDE.md` for complete instructions.
