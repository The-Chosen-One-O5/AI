# Telethon Userbot Setup Guide

This bot now uses Telethon in **userbot mode** instead of the traditional bot mode. This allows more flexibility and access to additional Telegram features.

## Prerequisites

### 1. Get API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click on "API development tools"
4. Create a new application (if you haven't already)
5. Copy your `api_id` and `api_hash`

### 2. Set Environment Variables

Create or update your `.env` file with the following credentials:

```bash
# Telegram Userbot Credentials (Required)
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE_NUMBER=+1234567890  # Your phone number in international format

# Session Configuration (Optional)
SESSION_PATH=userbot_session  # Default session file path
```

**Important Notes:**
- Use your actual phone number in international format (with country code)
- Keep these credentials secure and never commit them to version control
- The phone number should be the same one you use for Telegram

### 3. Other API Keys

Make sure you also have your other required API keys in the `.env` file:

```bash
# AI Service Keys
CEREBRAS_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
# ... (other keys as needed)
```

## First Run Authentication

When you run the bot for the first time, you'll need to authenticate:

1. Run the bot: `python main.py`
2. You'll receive a code via Telegram app (or SMS if app is not available)
3. Enter the code when prompted
4. If you have 2FA enabled, you'll also need to enter your password

```
🔐 TELEGRAM AUTHENTICATION REQUIRED
============================================================
Phone: +1234567890
Code sent via: Telegram app
============================================================
Enter the code you received: 12345

🔒 TWO-FACTOR AUTHENTICATION  # (Only if 2FA is enabled)
============================================================
Enter your 2FA password: ********
```

5. After successful authentication, a session file will be created
6. Future runs won't require authentication (session is reused)

## Session Files

- **Default location**: `userbot_session.session` in the project root
- **Custom location**: Set `SESSION_PATH` environment variable
- **Session persistence**: The session file persists across restarts
- **Session security**: Keep the `.session` file secure - it contains your authentication

## String Sessions (Cloud Deployment)

For cloud deployments (Render, Heroku, etc.) where file persistence is not reliable:

1. Generate a string session locally:
   ```python
   python userbot.py  # Run the userbot module directly
   ```

2. Copy the string session output
3. Set it as an environment variable:
   ```bash
   TELETHON_SESSION=your_long_string_session_here
   ```

4. Update config.json to use string sessions:
   ```json
   {
     "use_string_session": true
   }
   ```

## Error Handling

The userbot includes automatic error handling for:

- **Authentication failures**: Clear error messages with instructions
- **Flood wait**: Automatic waiting and retry
- **Network migration**: Automatic datacenter migration
- **Disconnection**: Auto-reconnect with exponential backoff (up to 5 attempts)
- **Invalid credentials**: Validation with helpful error messages

## Logs

Watch the logs for connection status:

```
🚀 Initializing Telethon userbot...
Connecting to Telegram...
✅ Session valid, user already authorized
✅ Logged in as: John Doe (@johndoe) [ID: 123456789]
✅ Userbot started successfully
✅ All event handlers registered
🤖 Userbot is running and connected...
```

## Troubleshooting

### Invalid API credentials
```
❌ Invalid API_ID or API_HASH
```
**Solution**: Double-check your API_ID and API_HASH from https://my.telegram.org

### Invalid phone number
```
❌ Invalid phone number format
```
**Solution**: Use international format with country code (e.g., +1234567890)

### Flood wait
```
❌ Flood wait: Need to wait 300 seconds
```
**Solution**: Wait the specified time. The bot will automatically wait and retry.

### Session file not persisting
**Solution**: 
- Check file permissions in the project directory
- For cloud deployment, use string sessions instead

### Client disconnected
```
Client disconnected, attempting to reconnect...
```
**Solution**: The bot automatically handles reconnection. If it fails after 5 attempts, restart the bot.

## Configuration

Session settings can be customized in `config.json`:

```json
{
  "session_path": "userbot_session",
  "use_string_session": false,
  "reminder_time": "04:00",
  ...
}
```

## Security Best Practices

1. **Never share** your API_ID, API_HASH, or session files
2. **Add to .gitignore**: Ensure `.env` and `*.session` files are gitignored
3. **Rotate credentials**: If credentials are compromised, revoke and create new ones
4. **2FA recommended**: Enable two-factor authentication on your Telegram account
5. **Session monitoring**: Telegram > Settings > Privacy > Active Sessions to monitor active sessions

## Features

The userbot mode provides:
- ✅ Full Telegram API access
- ✅ Voice call features (pytgcalls integration)
- ✅ Message handling as a user account
- ✅ Group chat management
- ✅ Persistent session across restarts
- ✅ Automatic reconnection on disconnect
- ✅ Flood wait handling

## Need Help?

- Check logs for detailed error messages
- Verify all environment variables are set correctly
- Ensure your phone number is correct and accessible
- Test authentication by running `python userbot.py` directly
