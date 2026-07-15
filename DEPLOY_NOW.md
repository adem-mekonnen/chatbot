# 🚀 Deploy Your Chatbot to Streamlit Cloud (Step-by-Step)

## ✅ Prerequisites (Already Done!)
- [x] Code pushed to GitHub: `adem-mekonnen/chatbot`
- [x] Branch: `deploy-fix` (clean, no secrets)
- [x] App tested locally and working
- [x] Requirements.txt has only `streamlit`

---

## 📋 Deployment Steps

### Step 1: Go to Streamlit Cloud
1. Open your browser and go to: **https://share.streamlit.io/**
2. Sign in with your GitHub account

### Step 2: Create New App (or Update Existing)

If you already have an app deployed:
1. Click on your existing app (e.g., `chatbot-gxbkio9qyz9tiaf7q4kndb`)
2. Click **"⚙️ Settings"** (top right)
3. Click **"Edit"**

If creating a new app:
1. Click **"New app"** button
2. Continue to configuration below

### Step 3: Configure Your App Settings

Fill in these **EXACT** values:

```
┌─────────────────────────────────────────────┐
│ Repository:  adem-mekonnen/chatbot          │
│ Branch:      deploy-fix                     │
│ Main file:   app-simple.py                  │
│ App URL:     (your-custom-name or leave it) │
└─────────────────────────────────────────────┘
```

### Step 4: Advanced Settings

Click **"Advanced settings"** and configure:

**Python version:**
```
3.11
```

**Secrets:** (Click "Add" if not visible)
```
JWT_SECRET_KEY = "test"
```

**IMPORTANT:** Remove ALL other secrets for now (HF_INFERENCE_TOKEN, DATABASE_URL, etc.)

### Step 5: Deploy!

1. Click **"Save"** (if editing existing app)
   OR
   Click **"Deploy!"** (if new app)

2. Wait 2-5 minutes for deployment

3. Watch the logs - you should see:
   ```
   ✅ Successfully installed streamlit
   ✅ App is running
   ```

---

## 🎯 Expected Result

Your app will be live at a URL like:
- `https://your-app-name.streamlit.app`

You should see:
1. 🔐 Login page with purple gradient background
2. Demo credentials shown in expandable section
3. Login form that accepts: alice/alice123, bob/bob123, admin/admin123

---

## 🔍 Troubleshooting

### If deployment fails:

**1. "Error installing requirements"**
- Check that `requirements.txt` only contains: `streamlit`
- Make sure you're using branch `deploy-fix`, NOT `main`

**2. "WebSocket connection failed"**
- This means the app is crashing on startup
- **Solution:** Use simpler app first:
  - Change main file to: `hello.py`
  - If that works, then try: `test.py`
  - Finally try: `app-simple.py`

**3. "Invalid credentials" after deployment**
- The app is working! Just type carefully:
  - Username: `alice` (lowercase)
  - Password: `alice123`

**4. App keeps restarting**
- Check the logs in Streamlit Cloud dashboard
- Look for Python errors
- Make sure all imports are available

---

## 📊 Deployment Configuration Summary

| Setting | Value |
|---------|-------|
| Repository | `adem-mekonnen/chatbot` |
| Branch | `deploy-fix` |
| Main file | `app-simple.py` |
| Python version | `3.11` |
| Dependencies | Only `streamlit` |
| Secrets | `JWT_SECRET_KEY = "test"` |

---

## 🎉 What Your App Can Do

Once deployed, users can:

1. **Login** with demo accounts
   - alice / alice123 (customer)
   - bob / bob123 (customer)
   - admin / admin123 (admin)

2. **Chat** with the AI assistant
   - Ask about account balance
   - Ask about vacation policy
   - Ask about benefits
   - Ask about remote work policy

3. **Quick Actions**
   - 💰 Check Balance button
   - 🏖️ Vacation Policy button
   - 💼 Benefits button

---

## 🔄 To Update Your Deployed App

Whenever you make changes locally:

```bash
# 1. Test locally first
streamlit run app-simple.py

# 2. Commit and push changes
git add .
git commit -m "your change description"
git push origin deploy-fix

# 3. Streamlit Cloud auto-deploys in 1-2 minutes!
```

---

## 📞 Need Help?

If something isn't working:
1. Check Streamlit Cloud logs (click "Manage app" → "Logs")
2. Make sure you're using `deploy-fix` branch
3. Verify `requirements.txt` only has `streamlit`
4. Try the simpler apps first: `hello.py` → `test.py` → `app-simple.py`

---

## 🎯 Next Steps After Deployment

Once `app-simple.py` works, you can:
1. Customize the UI colors and styling
2. Add more demo users
3. Add more chat responses
4. Integrate with real database
5. Add full AI/ML capabilities (requires more dependencies)

**Current Status:** Ready to deploy! 🚀
