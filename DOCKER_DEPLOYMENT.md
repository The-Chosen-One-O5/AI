# Docker Deployment Guide for Render

This guide explains how to deploy the AI618 bot on Render using Docker.

## Prerequisites

Before deploying, you need to generate a session string locally.

### Generate SESSION_STRING Locally

1. Install dependencies locally:
   ```bash
   pip install telethon python-dotenv
   ```

2. Create a `.env` file with your credentials:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   PHONE_NUMBER=+1234567890
   ```

3. Run the userbot test script:
   ```bash
   python userbot.py
   ```

4. Follow the authentication prompts (enter code, 2FA password if enabled)

5. Copy the SESSION_STRING that gets printed (it will look like: `1ApWapzM...` - a long string)

6. Save this SESSION_STRING - you'll need it for deployment!

## Environment Variables Required on Render

Set these in your Render web service environment variables:

### Required (Telegram Auth)
- `API_ID`: Your Telegram API ID from https://my.telegram.org
- `API_HASH`: Your Telegram API hash from https://my.telegram.org
- `PHONE_NUMBER`: Phone number in international format (e.g., +1234567890)
- `SESSION_STRING`: The session string you generated locally (see above)

### Required (Bot Functionality)
- `TARGET_CHAT_ID`: The chat ID where the bot should operate
- Other API keys as needed (see main.py for full list)

### Optional
- `PORT`: Port for Flask health server (default: 8080) - Render provides this automatically

## Deployment Steps

1. **Fork/Clone this repository**

2. **Create a new Web Service on Render**
   - Connect your GitHub repository
   - Select "Docker" as the environment
   - Render will automatically detect the Dockerfile

3. **Configure Environment Variables**
   - Add all required environment variables (especially SESSION_STRING)
   - Make sure SESSION_STRING is the one you generated locally

4. **Deploy**
   - Render will build the Docker image and deploy
   - The bot will start automatically
   - Flask server will respond on /health endpoint

## How It Works

### Docker Container

The Dockerfile does the following:
1. Uses Python 3.10 slim image
2. Installs FFmpeg (required for audio processing)
3. Installs Python dependencies (including pytgcalls which bundles tgcalls)
4. Exposes port 8080 for health checks
5. Runs two processes:
   - `keep_alive.py`: Flask server for health checks (required by Render)
   - `main.py`: The main bot process

### Session Management

The bot uses Telethon's StringSession for stateless authentication:
- **Local Development**: Uses file-based session (`userbot_session`)
- **Docker/Cloud**: Uses SESSION_STRING environment variable
- No interactive prompts in Docker - the bot will fail fast if SESSION_STRING is invalid

### Health Checks

Flask server provides two endpoints:
- `GET /`: Returns "Bot is running!"
- `GET /health`: Returns "OK"

Render uses these to monitor the service health.

## Troubleshooting

### "SESSION_STRING environment variable not set"
- You forgot to add SESSION_STRING to Render environment variables
- Generate it locally first using `python userbot.py`

### "Session not authorized! SESSION_STRING is invalid or expired"
- Your SESSION_STRING expired or was revoked
- Generate a new one locally and update Render environment variable

### "Invalid API_ID or API_HASH"
- Check that API_ID and API_HASH are correctly set in Render
- Get them from https://my.telegram.org

### Container keeps restarting
- Check Render logs for error messages
- Verify all required environment variables are set
- Make sure SESSION_STRING is valid

### Bot doesn't respond
- Verify TARGET_CHAT_ID is correct
- Check bot has necessary permissions in the chat
- Review Render logs for errors

## Important Notes

1. **Never commit SESSION_STRING to git** - it's like a password!
2. **Keep your API credentials secure** - use Render's environment variables
3. **Session strings can expire** - if the bot stops working, generate a new one
4. **The bot needs admin permissions** for moderation features
5. **FFmpeg is required** for voice/audio processing features

## Local Testing

To test the Docker setup locally:

```bash
# Build the image
docker build -t ai618bot .

# Run with environment variables
docker run -p 8080:8080 \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e PHONE_NUMBER=+1234567890 \
  -e SESSION_STRING=your_session_string \
  -e TARGET_CHAT_ID=-1001234567890 \
  ai618bot
```

Test health endpoint:
```bash
curl http://localhost:8080/health
```

## Support

If you encounter issues:
1. Check Render deployment logs
2. Verify all environment variables are set correctly
3. Ensure SESSION_STRING is valid and not expired
4. Check that API_ID, API_HASH, and PHONE_NUMBER match your Telegram account
