# 🚀 Free Deployment Guide - Enterprise AI Agent

**Complete Step-by-Step Instructions for Free Hosting**

---

## 📋 Table of Contents

1. [Recommended Free Hosting Options](#recommended-options)
2. [Option 1: Streamlit Community Cloud (Easiest)](#option-1-streamlit-cloud)
3. [Option 2: Render (Full Stack)](#option-2-render)
4. [Option 3: Railway (Full Stack)](#option-3-railway)
5. [Important Limitations & Solutions](#limitations)

---

## 🎯 Recommended Free Hosting Options

| Platform | Best For | Pros | Cons | Setup Time |
|----------|----------|------|------|------------|
| **Streamlit Cloud** | Quick demos | Easiest, 1-click deploy | Limited to Streamlit UI only | 5 mins |
| **Render** | Full stack | Backend + UI, auto-deploy | Need to run LLM remotely | 15 mins |
| **Railway** | Full stack | Easy setup, good free tier | Limited free hours | 15 mins |

**⚠️ IMPORTANT**: Free tiers don't support running Ollama (local LLM). We'll use **HuggingFace API** (free) instead.

---

## 🌟 Option 1: Streamlit Community Cloud (Recommended - Easiest)

**Best for**: Quick demos, presentations, testing  
**Cost**: 100% Free  
**Time**: ~5 minutes

### Prerequisites
- GitHub account
- HuggingFace account (free)

### Step 1: Get HuggingFace API Token

1. Go to https://huggingface.co/
2. Sign up for a free account (if you don't have one)
3. Click your profile picture → **Settings**
4. Go to **Access Tokens** on the left sidebar
5. Click **New token**
   - Name: `enterprise-agent`
   - Type: **Read**
6. Click **Generate token**
7. **Copy the token** - save it somewhere safe

### Step 2: Prepare Your Repository

1. **Push your code to GitHub** (if not already):
   ```bash
   # Initialize git (if needed)
   git init
   git add .
   git commit -m "Initial commit for deployment"
   
   # Create a new GitHub repository at https://github.com/new
   # Then push your code
   git remote add origin https://github.com/YOUR-USERNAME/enterprise-agent.git
   git branch -M main
   git push -u origin main
   ```

2. **Create a Streamlit-specific app file** (already exists: `app.py`)

### Step 3: Configure for Streamlit Cloud

Create a `.streamlit/secrets.toml` file (for local testing):

```bash
mkdir .streamlit
```

Then create the file with this content:

```toml
# .streamlit/secrets.toml
JWT_SECRET_KEY = "your-68-character-secret-key-here-make-it-very-secure-and-random"
DATABASE_URL = "sqlite+aiosqlite:///./enterprise_state.db"
CHROMA_PERSIST_DIR = "./vectorstore"
CHROMA_COLLECTION = "enterprise_docs"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:latest"
HF_INFERENCE_TOKEN = "your-huggingface-token-here"
USE_HUGGINGFACE_FALLBACK = "true"
```

**⚠️ IMPORTANT**: Add `.streamlit/secrets.toml` to your `.gitignore` so it's not pushed to GitHub!

```bash
echo ".streamlit/secrets.toml" >> .gitignore
```

### Step 4: Create Streamlit Config Files

Create `requirements.txt` (should already exist, but verify):

```bash
# Check if it has these packages
cat requirements.txt
```

Create `.streamlit/config.toml`:

```toml
[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```

### Step 5: Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click **New app**
3. Connect your GitHub account (if not already connected)
4. Select your repository: `enterprise-agent`
5. Set:
   - **Branch**: `main`
   - **Main file path**: `app.py`
6. Click **Advanced settings**
7. Add **Secrets** (same as `.streamlit/secrets.toml` content):
   ```
   JWT_SECRET_KEY = "your-secret-key"
   HF_INFERENCE_TOKEN = "your-huggingface-token"
   DATABASE_URL = "sqlite+aiosqlite:///./enterprise_state.db"
   CHROMA_PERSIST_DIR = "./vectorstore"
   USE_HUGGINGFACE_FALLBACK = "true"
   ```
8. Click **Deploy!**

### Step 6: Wait for Deployment

- Streamlit will install dependencies (2-3 minutes)
- Build the app
- Your app will be live at: `https://YOUR-APP-NAME.streamlit.app`

### Step 7: Test Your Deployment

1. Visit your app URL
2. Login with demo credentials: `alice` / `alice123`
3. Ask a question: "What is my account balance?"
4. Test the chatbot functionality

**✅ Done! Your app is live and free!**

---

## 🔧 Option 2: Render (Full Stack - Backend + UI)

**Best for**: Production-like deployment with separate backend  
**Cost**: Free (750 hours/month)  
**Time**: ~15 minutes

### Prerequisites
- GitHub account
- Render account (free - sign up at https://render.com)
- HuggingFace token (from Option 1)

### Step 1: Prepare Your Code

1. **Create `render.yaml`** in your project root:

```yaml
services:
  # FastAPI Backend
  - type: web
    name: enterprise-agent-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        value: sqlite+aiosqlite:///./enterprise_state.db
      - key: CHROMA_PERSIST_DIR
        value: ./vectorstore
      - key: CHROMA_COLLECTION
        value: enterprise_docs
      - key: HF_INFERENCE_TOKEN
        sync: false
      - key: USE_HUGGINGFACE_FALLBACK
        value: true
      - key: OLLAMA_URL
        value: http://localhost:11434
    healthCheckPath: /health
    
  # Streamlit UI
  - type: web
    name: enterprise-agent-ui
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0
    envVars:
      - key: API_URL
        fromService:
          name: enterprise-agent-api
          type: web
          property: url
```

2. **Update `ui/streamlit_app.py`** to use environment variable for API URL:

We'll need to modify the Streamlit app to read the API URL from environment variables.

3. **Push to GitHub**:
```bash
git add .
git commit -m "Add Render deployment config"
git push origin main
```

### Step 2: Deploy on Render

1. Go to https://dashboard.render.com
2. Click **New +** → **Blueprint**
3. Connect your GitHub repository
4. Select `enterprise-agent` repository
5. Render will detect `render.yaml` automatically
6. Click **Apply**
7. Set environment variables:
   - Click on the API service
   - Go to **Environment** tab
   - Add `HF_INFERENCE_TOKEN` with your token
8. Wait for both services to deploy (5-10 minutes)

### Step 3: Get Your URLs

After deployment:
- **API**: `https://enterprise-agent-api.onrender.com`
- **UI**: `https://enterprise-agent-ui.onrender.com`

**✅ Done! Your full-stack app is live!**

---

## 🚂 Option 3: Railway (Full Stack Alternative)

**Best for**: Easy deployment with good developer experience  
**Cost**: Free ($5 credit monthly)  
**Time**: ~15 minutes

### Step 1: Prepare Railway Config

1. **Create `railway.json`**:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
```

2. **Create `Procfile`** for Railway:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

3. **Push to GitHub**:
```bash
git add .
git commit -m "Add Railway deployment config"
git push origin main
```

### Step 2: Deploy on Railway

1. Go to https://railway.app
2. Sign up with GitHub
3. Click **New Project** → **Deploy from GitHub repo**
4. Select your `enterprise-agent` repository
5. Railway will auto-detect Python and deploy
6. Click on your service → **Variables** tab
7. Add environment variables:
   ```
   JWT_SECRET_KEY=your-secret-key-min-32-chars
   HF_INFERENCE_TOKEN=your-huggingface-token
   DATABASE_URL=sqlite+aiosqlite:///./enterprise_state.db
   CHROMA_PERSIST_DIR=./vectorstore
   USE_HUGGINGFACE_FALLBACK=true
   PORT=8000
   ```
8. Click **Settings** → **Generate Domain** to get public URL

### Step 3: Deploy Streamlit UI (Separate Service)

1. In Railway, click **New** → **GitHub Repo**
2. Select the same repository
3. Click **Settings** → Change start command to:
   ```
   streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```
4. Add environment variable:
   ```
   API_URL=https://your-api-url.railway.app
   ```
5. Generate domain for UI service

**✅ Done! Both services are live!**

---

## ⚙️ Important Modifications for Free Deployment

### 1. Update LLM Configuration

Since free hosting doesn't support running Ollama locally, we need to configure HuggingFace fallback.

**Modify `app/llm/client.py`** to prioritize HuggingFace:

```python
# Around line 20-30, update the initialization
def __init__(self):
    self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    self.hf_token = os.getenv("HF_INFERENCE_TOKEN")
    self.use_hf_fallback = os.getenv("USE_HUGGINGFACE_FALLBACK", "false").lower() == "true"
    
    # For free deployment, use HuggingFace by default
    if self.use_hf_fallback or not self._check_ollama_health():
        logger.info("Using HuggingFace API for LLM requests")
        self.primary_backend = "huggingface"
    else:
        self.primary_backend = "ollama"
```

### 2. Update Environment Variables

Add to your `.env` file:

```bash
USE_HUGGINGFACE_FALLBACK=true
HF_INFERENCE_TOKEN=your_token_here
```

### 3. Create `.gitignore` (if not exists)

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Database
*.db
*.sqlite3
enterprise_state.db

# Vector store
vectorstore/

# Environment
.env
.streamlit/secrets.toml

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## 🚨 Limitations & Solutions on Free Tier

### Limitation 1: No Ollama Support
**Solution**: Use HuggingFace Inference API (free tier: 30,000 characters/month)

```python
# Already implemented in app/llm/client.py
# Set USE_HUGGINGFACE_FALLBACK=true
```

### Limitation 2: SQLite Persistence
**Problem**: File storage may reset on free tier  
**Solution**: 
- For Streamlit Cloud: Use Streamlit's session state
- For Render/Railway: Upgrade to paid for persistent disk OR use PostgreSQL free tier

### Limitation 3: Vector Store Persistence
**Problem**: ChromaDB data may not persist  
**Solution**: Re-ingest documents on startup

**Add to `app/main.py`**:

```python
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    # Check if vector store exists, if not, reingest
    import os
    if not os.path.exists(os.getenv("CHROMA_PERSIST_DIR", "./vectorstore")):
        logger.info("Vector store not found, initializing...")
        from scripts.ingest import main as ingest_main
        ingest_main()
```

### Limitation 4: Cold Starts
**Problem**: Free tier services sleep after inactivity  
**Solution**: First request may be slow (30-60 seconds), subsequent requests are fast

### Limitation 5: Limited Memory/CPU
**Problem**: Heavy ML models may timeout  
**Solution**: Use smaller HuggingFace models (already configured)

---

## 🧪 Testing Your Deployment

After deployment, test these scenarios:

```bash
# Test 1: Health check
curl https://your-app-url/health

# Test 2: Authentication
curl -X POST https://your-app-url/token \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alice123"}'

# Test 3: Chat (replace TOKEN with actual token from Test 2)
curl -X POST https://your-app-url/chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is my balance?","session_id":"test-123"}'
```

---

## 📊 Free Tier Comparison

| Feature | Streamlit Cloud | Render | Railway |
|---------|----------------|--------|---------|
| **Cost** | Free forever | Free (750h/mo) | $5 credit/mo |
| **Services** | UI only | Multiple | Multiple |
| **Custom domain** | ❌ | ✅ | ✅ |
| **Auto-deploy** | ✅ | ✅ | ✅ |
| **Build time** | 2-3 min | 5-10 min | 3-5 min |
| **Cold starts** | ~10 sec | ~30 sec | ~15 sec |
| **SSL/HTTPS** | ✅ | ✅ | ✅ |
| **Easy setup** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎯 Recommended Deployment Path

### For Quick Demo/Testing:
→ **Streamlit Cloud** (5 minutes, easiest)

### For Production-like Setup:
→ **Render** (15 minutes, full-stack)

### For Best Free Tier:
→ **Railway** (15 minutes, generous limits)

---

## 🆘 Troubleshooting

### Issue: "Module not found" during deployment
**Solution**: Ensure `requirements.txt` is complete and in project root

### Issue: "Database locked" errors
**Solution**: Use async SQLite driver (already configured: `aiosqlite`)

### Issue: LLM timeout errors
**Solution**: Increase timeout in `.streamlit/config.toml`:
```toml
[server]
maxUploadSize = 200
maxMessageSize = 200
```

### Issue: App sleeps after inactivity
**Solution**: This is expected on free tier. Use uptime monitoring tools (free):
- UptimeRobot: https://uptimerobot.com (ping every 5 min)
- Cron-job.org: https://cron-job.org

### Issue: Out of memory
**Solution**: Reduce vector store size or use external vector DB (Pinecone free tier)

---

## 📞 Next Steps After Deployment

1. **Test thoroughly** with all user types (admin, alice, bob)
2. **Monitor usage** to stay within free tier limits
3. **Set up uptime monitoring** (UptimeRobot)
4. **Share your URL** with stakeholders
5. **Gather feedback** for improvements
6. **Consider upgrading** if you need:
   - More compute power
   - Persistent storage
   - Custom domain
   - Higher availability

---

## 🎉 Success Checklist

- [ ] HuggingFace account created and API token obtained
- [ ] Code pushed to GitHub
- [ ] Environment variables configured
- [ ] Deployment platform selected
- [ ] App deployed successfully
- [ ] Health check endpoint responding
- [ ] Login working with demo users
- [ ] Chat functionality tested
- [ ] Balance queries working
- [ ] Policy questions returning results

---

**Ready to deploy? Choose your platform and follow the steps above!**

For issues or questions, refer to the troubleshooting section or check the platform-specific documentation.

**Good luck with your deployment! 🚀**
