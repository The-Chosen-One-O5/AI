# Quick Start Guide

Get your bot running in 5 minutes! 🚀

## Choose Your Path

### Option A: Deploy to Render.com (Recommended)

**Best for**: Production use, 24/7 uptime

1. **Get Bot Token**
   ```
   Message @BotFather on Telegram → /newbot → Copy token
   ```

2. **Get AI API Key** (pick one)
   - Cerebras: https://cloud.cerebras.ai/
   - Groq: https://console.groq.com/
   - ChatAnywhere: https://chatanywhere.tech/

3. **Deploy to Render**
   - Go to https://dashboard.render.com
   - New + → Web Service
   - Connect GitHub repo
   - Add environment variables:
     - `BOT_TOKEN` = your bot token
     - `TARGET_CHAT_ID` = your group ID
     - `CEREBRAS_API_KEY` = your API key
   - Deploy!

4. **Test**
   ```
   In Telegram group:
   /start
   /boton
   /ai Hello!
   ```

**Done!** ✅

📖 **Detailed guide**: See `RENDER_DEPLOYMENT.md`  
✅ **Checklist**: See `DEPLOYMENT_CHECKLIST.md`  
📋 **Env vars**: See `RENDER_ENV_VARS.txt`

---

### Option B: Run Locally

**Best for**: Development, testing

1. **Clone & Install**
   ```bash
   git clone <your-repo>
   cd ai618-bot
   pip install -r requirements.txt
   ```

2. **Setup Environment**
   ```bash
   cp .env.example .env
   nano .env  # Add your credentials
   ```

3. **Run**
   ```bash
   python main.py
   ```

4. **Test**
   ```
   In Telegram:
   /start
   /boton
   /ai Hello!
   ```

**Done!** ✅

---

## Required Credentials

### 1. Telegram Bot Token (Required)
- Message [@BotFather](https://t.me/BotFather)
- Send `/newbot`
- Follow instructions
- Copy the token

### 2. Chat ID (Required)
- Add bot to your group
- Send any message
- Run `/chatid` command
- Copy the ID (like `-1001234567890`)

### 3. AI Provider (Pick ONE - Required)

**Option 1: Cerebras** (Recommended)
- Website: https://cloud.cerebras.ai/
- Model: llama3.1-70b
- Fast and reliable

**Option 2: Groq**
- Website: https://console.groq.com/
- Model: openai/gpt-oss-120b
- Good fallback option

**Option 3: ChatAnywhere**
- Website: https://chatanywhere.tech/
- Model: gpt-4o-mini
- Secondary fallback

### 4. Optional Services

**For image analysis** (`/askit`, `/nanoedit`):
- TypeGPT, Google AI, or OpenRouter

**For web search** (AI with live data):
- Brave Search API

**For audio** (`/audio` mode):
- Replicate API

**For video** (`/videoedit`):
- Samurai API

---

## First Commands

After deploying, try these in your Telegram group:

```bash
# Check if bot is alive
/start

# See all commands
/help

# Enable AI features (admin only)
/boton

# Check AI status
/aistatus

# Ask AI a question
/ai What is 2+2?

# Web search enabled AI
/ai What's the latest news about AI?

# Generate image description
/askit [reply to an image]

# Generate sticker
/ai sticker of a happy cat

# Start trivia game
/ai start trivia on science 5Q
```

---

## Troubleshooting

### "Bot not responding"
- ✅ Check bot is running (Render logs or terminal)
- ✅ Verify BOT_TOKEN is correct
- ✅ Make sure bot is in the group

### "AI not working"
- ✅ Run `/aistatus` to check if enabled
- ✅ Run `/boton` to enable (admin only)
- ✅ Verify at least one AI API key is set

### "Render deployment failed"
- ✅ Check build logs
- ✅ Verify all required env vars are set
- ✅ Ensure BOT_TOKEN is correct

---

## Next Steps

### Learn More
- 📖 **Full Documentation**: `README.md`
- 🚀 **Render Guide**: `RENDER_DEPLOYMENT.md`
- ✅ **Deployment Checklist**: `DEPLOYMENT_CHECKLIST.md`
- 📝 **What Changed**: `RESTORATION_SUMMARY.md`

### Get More API Keys
See `RENDER_DEPLOYMENT.md` → "Getting API Keys" section

### Add Features
Check `README.md` for all available commands and features

---

## Support

**Issues?**
- Check logs (Render dashboard or terminal)
- Review documentation files
- Check Telegram Bot API status

**Common Links**:
- Render Dashboard: https://dashboard.render.com
- BotFather: https://t.me/BotFather
- Telegram Bot API: https://core.telegram.org/bots/api

---

## File Reference

```
📁 Project Structure
│
├── 📄 QUICKSTART.md              ← You are here!
├── 📄 README.md                  ← Full documentation
├── 📄 RENDER_DEPLOYMENT.md       ← Render.com guide
├── 📄 DEPLOYMENT_CHECKLIST.md    ← Step-by-step checklist
├── 📄 RENDER_ENV_VARS.txt        ← Environment variables list
├── 📄 RESTORATION_SUMMARY.md     ← What was changed
├── 📄 COMPLETION_SUMMARY.md      ← Task completion details
│
├── 📄 .env.example               ← Template for local .env
├── 🐍 main.py                    ← Main bot code
├── 🐍 keep_alive.py              ← Keep-alive server
└── 📄 requirements.txt           ← Python dependencies
```

---

**Time to deploy**: ~5 minutes  
**Difficulty**: Easy ⭐  
**Cost**: Free (Render free tier)

**Let's go!** 🚀
