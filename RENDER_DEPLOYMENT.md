# Deploying to Render.com

This guide explains how to deploy the AI618 Telegram Bot to Render.com.

## Prerequisites

1. A [Render.com](https://render.com) account (free tier available)
2. Your bot token from [@BotFather](https://t.me/BotFather)
3. At least one AI provider API key (Cerebras, Groq, or ChatAnywhere)
4. Your GitHub repository connected to Render

## Deployment Steps

### 1. Create a New Web Service

1. Log in to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select the repository containing this bot

### 2. Configure the Service

**Basic Settings:**
- **Name:** `ai618-bot` (or your preferred name)
- **Environment:** `Python 3`
- **Region:** Choose closest to your users
- **Branch:** `main` (or your working branch)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`

**Instance Type:**
- **Free tier** is sufficient for moderate usage
- Upgrade to **Starter** ($7/month) if you need more reliability

### 3. Set Environment Variables

In the Render dashboard, add these environment variables:

#### Required Variables

```bash
# Telegram Bot (REQUIRED)
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Target Chat ID (your group ID)
TARGET_CHAT_ID=-1001234567890

# At least ONE AI provider is required:
CEREBRAS_API_KEY=your_cerebras_api_key
# OR
GROQ_API_KEY=your_groq_api_key
# OR
CHATANYWHERE_API_KEY=your_chatanywhere_api_key
```

#### Optional Variables (for additional features)

```bash
# Vision AI (for /askit, /nanoedit commands)
TYPEGPT_FAST_API_KEY=your_typegpt_key
GOOGLE_API_KEY=your_google_key
OPENROUTER_API_KEY=your_openrouter_key

# Web Search (for AI web search)
BRAVE_API_KEY=your_brave_api_key

# Audio Generation (for /audio mode)
REPLICATE_API_KEY=your_replicate_key

# Video Generation (for /videoedit, video generation)
SAMURAI_API_KEY=your_samurai_key

# Other providers
FALLBACK_API_KEY=your_fallback_key
GROK_API_KEY=your_grok_key
```

**Note:** The `PORT` environment variable is automatically set by Render (usually 8080).

### 4. Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Install dependencies from `requirements.txt`
   - Start the bot with `python main.py`
   - Keep it running 24/7

### 5. Verify Deployment

1. Check the **Logs** tab in Render dashboard
2. Look for these success messages:
   ```
   Keep-alive server started.
   Bot is running...
   ```
3. Test your bot in Telegram:
   ```
   /start
   /help
   /ai Hello!
   ```

## How It Works

### Keep-Alive Mechanism
- The bot runs a Flask HTTP server on the PORT provided by Render
- Render monitors this endpoint to ensure the bot stays alive
- The endpoint responds at `http://your-app.onrender.com/`

### Polling vs Webhooks
- This bot uses **polling mode** (no webhook setup needed)
- The bot actively polls Telegram's servers for updates
- No need to configure webhook URLs or SSL certificates

## Troubleshooting

### Bot Not Responding

1. **Check Logs:**
   - Go to Render Dashboard → Your Service → Logs
   - Look for error messages

2. **Verify Environment Variables:**
   - Ensure `BOT_TOKEN` is correct
   - Check at least one AI provider key is set

3. **Check Bot Status:**
   - Message [@BotFather](https://t.me/BotFather)
   - Ensure your bot is not disabled

### "FATAL ERROR: BOT_TOKEN environment variable not set!"

- Go to Render Dashboard → Your Service → Environment
- Add the `BOT_TOKEN` variable
- Click **"Save Changes"** (this will redeploy)

### AI Features Not Working

1. Check AI provider API keys are set correctly
2. Test AI status in your group: `/aistatus`
3. Enable AI if disabled: `/boton`
4. Check API provider quotas/limits

### Bot Keeps Crashing

1. **Check Dependencies:**
   - Ensure `requirements.txt` is up to date
   - Check build logs for installation errors

2. **Memory Issues:**
   - Free tier has 512 MB RAM limit
   - Upgrade to Starter tier if needed

3. **Rate Limits:**
   - AI providers may rate-limit on free tiers
   - Bot will fallback to alternative providers

## Monitoring

### Health Check
- Render automatically monitors: `http://your-app.onrender.com/`
- Returns `"I'm alive!"` when healthy
- Add a custom health check endpoint if needed: `http://your-app.onrender.com/health`

### Logs
- View real-time logs in Render Dashboard
- Logs include:
  - Bot startup messages
  - Command executions
  - API calls and errors
  - Health check pings

### Alerts
- Enable email notifications in Render settings
- Get alerted when service goes down

## Cost Optimization

### Free Tier Limitations
- Service spins down after 15 minutes of inactivity
- Spins back up on first request (may take 30-60 seconds)
- 750 hours/month of free usage

### Paid Tier Benefits ($7/month)
- Always on (no spin-down)
- Better performance
- More reliable for production use

### Reducing Costs
1. Use free AI provider tiers when possible
2. Optimize API calls to reduce usage
3. Consider deploying only for specific hours if usage is low

## Updating the Bot

### Automatic Deployment
- Push changes to your GitHub repository
- Render automatically detects changes
- Redeploys with new code

### Manual Deployment
1. Go to Render Dashboard → Your Service
2. Click **"Manual Deploy"**
3. Select branch to deploy

## Getting API Keys

### Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow instructions to create bot
4. Copy the token provided

### Cerebras API Key
1. Visit [Cerebras Cloud](https://cloud.cerebras.ai/)
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key

### Groq API Key
1. Visit [Groq Cloud](https://console.groq.com/)
2. Sign up for an account
3. Go to API Keys
4. Create a new API key

### ChatAnywhere API Key
1. Visit [ChatAnywhere](https://chatanywhere.tech/)
2. Sign up and get API key
3. Copy the key

### Other Providers
- **Brave Search:** https://brave.com/search/api/
- **Replicate:** https://replicate.com/
- **TypeGPT:** Contact provider for API access
- **OpenRouter:** https://openrouter.ai/

## Security Best Practices

1. **Never commit `.env` file** to Git (already in `.gitignore`)
2. **Use Render's environment variables** instead of `.env` file in production
3. **Rotate API keys** periodically
4. **Monitor usage** to detect unauthorized access
5. **Keep dependencies updated:** `pip install -r requirements.txt --upgrade`

## Support

- **Bot Issues:** Check logs and README.md
- **Render Support:** https://render.com/docs
- **Telegram Bot API:** https://core.telegram.org/bots/api

## Quick Reference

### Essential Commands (in Telegram)
```bash
/start          # Start the bot
/help           # Show all commands
/ai [query]     # Ask AI a question
/boton          # Enable AI features
/aistatus       # Check AI status
/chatid         # Get your chat ID
```

### Essential Render Dashboard Links
- **Logs:** Your Service → Logs tab
- **Environment:** Your Service → Environment tab
- **Metrics:** Your Service → Metrics tab
- **Deploy:** Your Service → Manual Deploy button

---

**Deployment Platform:** Render.com  
**Bot Framework:** python-telegram-bot  
**Authentication:** BOT_TOKEN only (no userbot/session files)  
**Keep-Alive:** Flask HTTP server on PORT  
**Update Mode:** Polling (no webhooks)
