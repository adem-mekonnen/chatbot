# 🚀 Quick Deploy - 5 Minute Guide

**Deploy your Enterprise AI Agent to Streamlit Cloud in 5 minutes!**

---

## 📋 What You Need

- ✅ GitHub account
- ✅ HuggingFace account (free)
- ✅ 5 minutes

---

## Step 1: Get HuggingFace Token (2 minutes)

1. Go to: https://huggingface.co
2. Click **Sign Up** (if you don't have an account)
3. After login, click your profile picture → **Settings**
4. Click **Access Tokens** in left sidebar
5. Click **New token**
   - Name: `enterprise-agent`
   - Type: Select **Read**
6. Click **Generate token**
7. **COPY THE TOKEN** → Save it somewhere (you'll need it in Step 3)

---

## Step 2: Push to GitHub (1 minute)

Open your terminal in the project folder and run:

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Ready for deployment"

# Create a new repository at https://github.com/new
# Name it: enterprise-agent
# Then connect and push:

git remote add origin https://github.com/YOUR-USERNAME/enterprise-agent.git
git branch -M main
git push -u origin main
```

**Replace `YOUR-USERNAME` with your actual GitHub username!**

---

## Step 3: Deploy on Streamlit Cloud (2 minutes)

### 3.1 Go to Streamlit Cloud
- Visit: https://share.streamlit.io
- Click **Sign in with GitHub**
- Authorize Streamlit to access your repositories

### 3.2 Create New App
- Click **New app** button
- Fill in the form:
  - **Repository**: Select `enterprise-agent`
  - **Branch**: `main`
  - **Main file path**: `app.py`

### 3.3 Add Secrets
- Click **Advanced settings** (bottom of form)
- In the **Secrets** text box, paste this (replace the values):

```toml
JWT_SECRET_KEY = "your-very-long-random-secret-key-at-least-32-characters-long-and-secure"
HF_INFERENCE_TOKEN = "paste-your-huggingface-token-here"
DATABASE_URL = "sqlite+aiosqlite:///./enterprise_state.db"
CHROMA_PERSIST_DIR = "./vectorstore"
CHROMA_COLLECTION = "enterprise_docs"
USE_HUGGINGFACE_FALLBACK = "true"
```

**Important**: 
- Replace `JWT_SECRET_KEY` with a long random string (mash your keyboard!)
- Replace `HF_INFERENCE_TOKEN` with the token from Step 1

### 3.4 Deploy!
- Click **Deploy!** button
- Wait 2-3 minutes while Streamlit builds your app
- Watch the logs to see progress

---

## Step 4: Test Your App (30 seconds)

### Your app is live! 🎉

1. **Get your URL**: `https://YOUR-APP-NAME.streamlit.app`
2. **Open in browser**
3. **Login** with demo credentials:
   - Username: `alice`
   - Password: `alice123`
4. **Try asking**:
   - "What is my account balance?"
   - "What are the vacation policies?"
   - "Tell me about company benefits"

---

## ✅ Success Checklist

- [x] HuggingFace token obtained
- [x] Code pushed to GitHub
- [x] App deployed to Streamlit Cloud
- [x] Secrets configured
- [x] App is live and accessible
- [x] Can login with demo users
- [x] Chat functionality working

---

## 🎯 Your App is LIVE!

**Share your app URL with others**:
```
https://YOUR-APP-NAME.streamlit.app
```

**Demo Credentials** (share these with users):
- Customer Account: `alice` / `alice123`
- Admin Account: `admin` / `admin123`

---

## 🔧 Need to Update Your App?

Just push changes to GitHub:

```bash
git add .
git commit -m "Updated feature"
git push origin main
```

Streamlit Cloud will automatically redeploy! 🚀

---

## 🆘 Troubleshooting

### App won't start?
**Check**: Did you add all secrets correctly? Especially the HuggingFace token?

### Login not working?
**Check**: The app takes 30-60 seconds on first load. Try refreshing.

### LLM not responding?
**Check**: HuggingFace free tier has rate limits. Wait a minute and try again.

### Can't find my app?
**Check**: Go to https://share.streamlit.io/workspaces → Your apps are listed there

---

## 📊 Free Tier Limits

| Resource | Limit | What It Means |
|----------|-------|---------------|
| Apps | 3 public apps | You can deploy 3 apps |
| CPU | 1 vCPU | Shared compute |
| Memory | 1 GB RAM | Enough for this app |
| Sleep | After 7 days inactive | Wake on first access |

**These limits are fine for demos and testing!**

---

## 🎓 Next Steps

### Make it yours:
1. Change demo user passwords (see `scripts/setup_demo_users.py`)
2. Add more knowledge base documents (`data/knowledge_base/`)
3. Customize the UI colors and branding
4. Add your own logo

### Share it:
- Post on LinkedIn
- Show to your team
- Add to your portfolio
- Use for demos and presentations

---

## 🎉 Congratulations!

You've successfully deployed an enterprise AI chatbot to the cloud in 5 minutes!

**Want more control?** See `FREE_DEPLOYMENT_GUIDE.md` for full-stack deployment on Render or Railway.

**Need help?** Check `DEPLOYMENT_CHECKLIST.md` for detailed troubleshooting.

---

**Your deployed app**: https://YOUR-APP-NAME.streamlit.app 🚀
