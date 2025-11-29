# AI618 Telegram Bot

A comprehensive AI-powered Telegram bot with trivia games, image/video generation, and advanced chat management features.

> **🚀 New to this bot?** Start with **[QUICKSTART.md](QUICKSTART.md)** for a 5-minute setup guide!

## Features

### 🤖 AI Assistant
- **Multi-Provider Fallback**: Cerebras → Groq → ChatAnywhere for maximum reliability
- **Web Search Integration**: Brave API for real-time information
- **Context-Aware**: Maintains chat history for coherent conversations
- **Proactive Engagement**: Random chat injections and emoji reactions

### 🎮 Interactive Features
- **Trivia Games**: Multi-player quiz system with leaderboards
- **Gossip Memory**: Save and recall memorable messages
- **Chat Summaries**: AI-generated conversation summaries

### 🎨 Creative Tools
- **AI Stickers**: Generate custom stickers from text prompts
- **Image Analysis**: Vision AI for image description and Q&A
- **Video Generation**: Text-to-video and image-to-video creation
- **LaTeX Rendering**: Mathematical expressions
- **Molecular Structures**: SMILES to chemical structure images

### 🎤 Text-to-Speech
- **Free & Unlimited**: Microsoft Edge TTS (no API costs) or Premium TTS API
- **Multiple Voices**: 9+ voice options including deep male and female voices
- **Speak Mode**: Toggle audio-only responses with `/speak` command - bot responds exclusively with audio messages
- **Voice Selection**: Choose from 11+ premium voices with `/ttsvoice` (alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse)
- **Per-User Configuration**: Individual voice preferences saved per user
- **High Quality**: Neural TTS with natural-sounding speech and emotion support

### 🛡️ Moderation & Admin
- **User Management**: Ban, mute, unmute users
- **Message Control**: Delete messages, lock/unlock chats
- **Feature Toggles**: Enable/disable AI, random chat, moderation per group
- **Daily Reminders**: Configurable exam countdown reminders

## Quick Start

### Prerequisites
- Python 3.10+
- Telegram Bot Token (from @BotFather)
- API Keys (see Configuration section)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai618-bot
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (see Configuration)

4. Run the bot:
```bash
python main.py
```

### Cloud Deployment (Render.com)

For production deployment on Render.com, see the comprehensive guide:
- **[RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)** - Complete Render.com deployment instructions

Quick steps:
1. Connect your GitHub repo to Render
2. Create a new Web Service
3. Set environment variables in Render dashboard
4. Deploy automatically

## Configuration

### Required Environment Variables

For local development, copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Then edit .env with your actual API keys
```

Or create a `.env` file manually with:

```bash
# Essential
BOT_TOKEN=your_telegram_bot_token
TARGET_CHAT_ID=-1001234567890  # Your group chat ID

# AI Providers (at least one required)
CEREBRAS_API_KEY=your_cerebras_key
GROQ_API_KEY=your_groq_key
CHATANYWHERE_API_KEY=your_chatanywhere_key

# For web search (optional)
BRAVE_API_KEY=your_brave_api_key

# For vision features (optional)
TYPEGPT_FAST_API_KEY=your_typegpt_key
OPENROUTER_API_KEY=your_openrouter_key

# For video generation (optional)
SAMURAI_API_KEY=your_samurai_key
```

### Configuration Files

The bot creates and manages these JSON files:
- `config.json`: Non-sensitive settings (toggles, etc.)
- `memory.json`: Persistent memory for facts
- `gossip.json`: Saved memorable messages

## Command Reference

### Core Commands

```
/start, /help          - Show help message
/ai [query]           - Ask AI a question (includes web search)
/chatid               - Get current chat ID
```

### AI Features

```
/ai start trivia on [topic] [num]Q  - Start trivia game (Admin)
/ai stop trivia                      - Stop current game (Admin)
/ai remember this                    - Save replied message (reply)
/ai gossip                           - Recall random saved message
/ai sticker of [prompt]              - Generate AI sticker
/ai video of [prompt]                - Generate AI video
```

### Image Commands

```
/askit [prompt]     - Ask about an image (reply to image)
/nanoedit [prompt]  - Edit/describe image with AI (reply to image)
/videoedit [prompt] - Generate video from image (reply to image)
```

### Utility Commands

```
/chem [SMILES]         - Draw chemical structure
/tex [LaTeX]           - Render LaTeX expression
/summarize             - Summarize recent chat
/studypoll "Q" "A1" .. - Create study poll (Admin)
/audio                 - Generate audio from text (Edge TTS)
/audioselect [voice]   - Select Edge TTS voice (guy, jenny, aria, brian, sonia)
/speak                 - Toggle Speak Mode (AI responds ONLY with audio, no text)
/ttsvoice [voice]      - Select TTS voice for Speak Mode (alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse)
```

### Memory Commands

```
/remember topic = fact  - Save a fact
/recall [topic]         - Recall fact (empty for list)
/forget [topic]         - Forget a fact
```

### Admin Settings

```
/boton, /botoff        - AI features ON/OFF
/aistatus              - Check AI status
/randomon, /randomoff  - Random chat ON/OFF
/randomstatus          - Check random chat status
/testrandom            - Trigger random chat now
/on, /off              - Moderation ON/OFF
/time HH:MM            - Set reminder time (IST)
```

### Moderation (Admin only)

```
/ban      - Ban user (reply to user)
/mute     - Mute user (reply to user)
/unmute   - Unmute user (reply to user)
/delete   - Delete message (reply to message)
/lock     - Lock chat (prevent messages)
/unlock   - Unlock chat
```

## Architecture

### Core Components
- **main.py**: Main bot logic
- **keep_alive.py**: Flask server for uptime monitoring
- **Configuration**: JSON-based persistence

### AI Provider Chain
1. **Primary**: Cerebras (llama3.1-70b)
2. **Fallback 1**: Groq (openai/gpt-oss-120b)
3. **Fallback 2**: ChatAnywhere (gpt-4o-mini)

### Vision Models
- **Primary**: TypeGPT Fast (gemini-2.5-pro)
- **Fallback**: OpenRouter (moonshotai/kimi-vl-a3b-thinking:free)

## Dependencies

Core libraries:
- `python-telegram-bot` - Telegram Bot API
- `httpx` - Async HTTP client
- `cerebras-cloud-sdk` - Cerebras AI
- `groq` - Groq API
- `openai` - OpenAI-compatible clients
- `edge-tts` - Free text-to-speech (Microsoft Edge)
- `replicate` - Video generation
- `rdkit` - Chemistry structures
- `Pillow` - Image processing
- `BeautifulSoup4` - Web scraping
- `telegraph` - Long response publishing
- `emoji` - Emoji handling
- `pytz` - Timezone support
- `Flask` - Keep-alive server

## Safety & Privacy

### Data Retention
- **Chat History**: Last 30 messages (in-memory)
- **Persistent Storage**: Only config, memory, and gossip JSON files

### User Control
- Admins can enable/disable all features per chat
- Clear status commands for transparency

## Development

### Project Structure
```
.
├── main.py                 # Main bot logic
├── keep_alive.py          # Uptime server
├── requirements.txt       # Dependencies
├── config.json           # Runtime configuration
├── memory.json           # Persistent facts
├── gossip.json           # Saved messages
└── README.md            # This file
```

### Adding New Commands

1. Create async handler function:
```python
async def my_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello!")
```

2. Register in `main()`:
```python
CommandHandler("mycommand", my_command_handler)
```

### Code Conventions
- Async/await for all I/O operations
- Try/except blocks for external API calls
- Logging for debugging and monitoring
- Type hints where practical
- Config persistence for user settings

## Troubleshooting

### Bot Not Responding
1. Check bot is running: `ps aux | grep main.py`
2. Check API keys in `.env`
3. Check logs for errors
4. Verify bot is in the group
5. Check if AI is enabled: `/aistatus`

### API Rate Limits
- Each provider has different limits
- Bot automatically falls back to alternative providers
- Consider upgrading API plans if hitting limits frequently

## Contributing

Contributions welcome! Please:
1. Test changes thoroughly
2. Follow existing code style
3. Update documentation
4. Add logging for new features
5. Handle errors gracefully

## License

[Your License Here]

## Credits

- Built with [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- AI by Cerebras, Groq, and OpenAI-compatible providers
- Image generation by various APIs

## Support

For issues, feature requests, or questions:
- Review logs for error messages
- Test with minimal configuration first

---

**Version**: 1.0.0
**Last Updated**: 2024
**Status**: Production Ready
