# Deployment Checklist for Render.com

Use this checklist to ensure successful deployment of your AI618 Telegram Bot to Render.com.

## Pre-Deployment

### 1. Get Your Credentials

- [ ] **Telegram Bot Token**
  - Message [@BotFather](https://t.me/BotFather)
  - Create new bot: `/newbot`
  - Copy the BOT_TOKEN

- [ ] **Target Chat ID**
  - Add your bot to your group
  - Send a message in the group
  - Use `/chatid` command to get the chat ID
  - Or visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`

- [ ] **At Least One AI Provider API Key** (Required)
  - [ ] Cerebras: https://cloud.cerebras.ai/
  - [ ] Groq: https://console.groq.com/
  - [ ] ChatAnywhere: https://chatanywhere.tech/

- [ ] **Optional API Keys** (For additional features)
  - [ ] Brave Search (web search): https://brave.com/search/api/
  - [ ] Replicate (audio): https://replicate.com/
  - [ ] TypeGPT (vision): Contact provider
  - [ ] OpenRouter (vision): https://openrouter.ai/
  - [ ] Samurai (video): Contact provider

### 2. Prepare Repository

- [ ] Code is pushed to GitHub
- [ ] `.env` file is **NOT** committed (check `.gitignore`)
- [ ] All dependencies are in `requirements.txt`
- [ ] `keep_alive.py` is present
- [ ] `main.py` is present

## Render.com Setup

### 3. Create Web Service

- [ ] Log in to [Render Dashboard](https://dashboard.render.com)
- [ ] Click "New +" → "Web Service"
- [ ] Connect your GitHub account
- [ ] Select your repository
- [ ] Configure service:
  ```
  Name: ai618-bot
  Environment: Python 3
  Build Command: pip install -r requirements.txt
  Start Command: python main.py
  Instance Type: Free (or Starter)
  ```

### 4. Configure Environment Variables

Go to Environment tab and add these variables:

#### Required Variables (Minimum Setup)

- [ ] `BOT_TOKEN` = `your_bot_token_from_botfather`
- [ ] `TARGET_CHAT_ID` = `your_group_chat_id` (e.g., `-1001234567890`)
- [ ] `CEREBRAS_API_KEY` = `your_cerebras_key` (or Groq/ChatAnywhere)

#### Optional Variables (Add as needed)

- [ ] `GROQ_API_KEY` = `your_groq_key`
- [ ] `CHATANYWHERE_API_KEY` = `your_chatanywhere_key`
- [ ] `BRAVE_API_KEY` = `your_brave_key`
- [ ] `REPLICATE_API_KEY` = `your_replicate_key`
- [ ] `TYPEGPT_FAST_API_KEY` = `your_typegpt_key`
- [ ] `GOOGLE_API_KEY` = `your_google_key`
- [ ] `OPENROUTER_API_KEY` = `your_openrouter_key`
- [ ] `SAMURAI_API_KEY` = `your_samurai_key`
- [ ] `FALLBACK_API_KEY` = `your_fallback_key`
- [ ] `GROK_API_KEY` = `your_grok_key`

**Note:** PORT is automatically set by Render (no need to add it manually)

### 5. Deploy

- [ ] Click "Create Web Service" or "Manual Deploy"
- [ ] Wait for deployment to complete (usually 2-5 minutes)
- [ ] Check logs for success messages:
  ```
  Keep-alive server started.
  Bot is running...
  ```

## Post-Deployment Testing

### 6. Verify Bot is Running

- [ ] Check Render logs show no errors
- [ ] Visit health endpoint: `https://your-app.onrender.com/` (should show "I'm alive!")
- [ ] Bot should be online in Telegram

### 7. Test Bot Commands

In your Telegram group, test these commands:

- [ ] `/start` - Shows welcome message
- [ ] `/help` - Shows command list
- [ ] `/chatid` - Shows current chat ID
- [ ] `/aistatus` - Shows AI status
- [ ] `/boton` - Enables AI features (if you're admin)
- [ ] `/ai Hello!` - Tests AI response

### 8. Enable Features

- [ ] Run `/boton` to enable AI features
- [ ] Test AI: `/ai Tell me a joke`
- [ ] Test vision (if configured): `/askit` (reply to an image)
- [ ] Test trivia: `/ai start trivia on science 5Q`

## Troubleshooting

### Bot Not Responding

- [ ] Check Render logs for errors
- [ ] Verify `BOT_TOKEN` is correct in environment variables
- [ ] Verify bot is not disabled in @BotFather
- [ ] Check if service is running (not crashed)

### AI Features Not Working

- [ ] Verify at least one AI provider key is set
- [ ] Run `/aistatus` to check if AI is enabled
- [ ] Run `/boton` to enable AI
- [ ] Check API provider quotas/limits
- [ ] Check Render logs for API errors

### Service Keeps Crashing

- [ ] Check build logs for dependency errors
- [ ] Verify all required environment variables are set
- [ ] Check if you're hitting free tier memory limits
- [ ] Consider upgrading to Starter tier ($7/month)

### "FATAL ERROR: BOT_TOKEN environment variable not set!"

- [ ] Add `BOT_TOKEN` to environment variables in Render dashboard
- [ ] Save changes and redeploy
- [ ] Check logs to confirm it's set

## Maintenance

### Regular Tasks

- [ ] Monitor Render logs for errors
- [ ] Check API usage/quotas regularly
- [ ] Update bot commands with `/help` when adding features
- [ ] Keep dependencies updated periodically

### When Updating Code

- [ ] Push changes to GitHub
- [ ] Render auto-deploys (if enabled)
- [ ] Or click "Manual Deploy" in Render dashboard
- [ ] Monitor logs during deployment
- [ ] Test bot after deployment

## Cost Management

### Free Tier

- [ ] Service spins down after 15 minutes of inactivity
- [ ] ~30-60 seconds to spin back up on first request
- [ ] 750 hours/month free usage

### Upgrading to Paid ($7/month)

Reasons to upgrade:
- [ ] Need 24/7 uptime (no spin-down)
- [ ] Hitting memory limits (free: 512 MB)
- [ ] Want better performance
- [ ] Need more reliability

## Security

- [ ] `.env` file is in `.gitignore` (never commit secrets)
- [ ] Use Render's environment variables (not `.env` in production)
- [ ] Rotate API keys periodically
- [ ] Monitor for unusual activity
- [ ] Keep dependencies updated for security patches

## Resources

- [ ] **Bot Documentation**: See README.md
- [ ] **Deployment Guide**: See RENDER_DEPLOYMENT.md
- [ ] **Restoration Info**: See RESTORATION_SUMMARY.md
- [ ] **Render Docs**: https://render.com/docs
- [ ] **Telegram Bot API**: https://core.telegram.org/bots/api
- [ ] **Support Issues**: Check GitHub Issues

---

## Quick Reference

### Essential URLs
- Render Dashboard: https://dashboard.render.com
- Your Service: https://dashboard.render.com/web/[YOUR_SERVICE_ID]
- Bot Health Check: https://your-app.onrender.com/
- Telegram Bot Management: https://t.me/BotFather

### Essential Commands (in Telegram)
```
/start          # Start the bot
/help           # Show all commands
/chatid         # Get current chat ID
/aistatus       # Check AI status
/boton          # Enable AI features (admin)
/ai [query]     # Ask AI a question
```

### Emergency Commands
```bash
# View logs in terminal (if you have Render CLI)
render logs -t [SERVICE_ID]

# Restart service
# Go to Render Dashboard → Your Service → Manual Deploy → Deploy Latest Commit
```

---

**Deployment Status**: 
- [ ] ✅ Successfully deployed
- [ ] ⏳ In progress
- [ ] ❌ Needs troubleshooting

**Last Updated**: _______________

**Notes**:
```
[Add any deployment-specific notes here]
```
