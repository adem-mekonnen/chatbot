# ⚡ Quick Deploy Guide - 5 Minutes

## 🎯 Deploy Your Chatbot in 5 Simple Steps

### Step 1: Go to Streamlit Cloud
👉 **https://share.streamlit.io/** (sign in with GitHub)

### Step 2: Create or Edit Your App
- **New app?** Click "New app" button
- **Existing app?** Click your app → Settings → Edit

### Step 3: Use These EXACT Settings

```
Repository:     adem-mekonnen/chatbot
Branch:         deploy-fix
Main file:      app-simple.py
Python:         3.11
```

**Secrets (Advanced settings):**
```
JWT_SECRET_KEY = "test"
```
(Remove all other secrets!)

### Step 4: Click "Deploy!" or "Save"
⏳ Wait 2-5 minutes

### Step 5: Test Your App
Login with:
- Username: `alice`
- Password: `alice123`

---

## ✅ That's It!

Your chatbot is now live at: `https://your-app-name.streamlit.app`

---

## 🚨 If It Doesn't Work

**Try starting simpler:**
1. Change main file to: `hello.py` → Save → Wait
2. If works, change to: `test.py` → Save → Wait
3. If works, change to: `app-simple.py` → Save → Wait

---

## 📚 More Details?

- Full guide: `DEPLOY_NOW.md`
- Visual guide: `STREAMLIT_CLOUD_GUIDE.md`

---

**Ready? Go to https://share.streamlit.io/ now!** 🚀
