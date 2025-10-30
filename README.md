# AI618 Telegram Bot

A comprehensive AI-powered Telegram bot with proactive call participation, trivia games, image/video generation, and advanced chat management features.

## Features

### 🎤 Voice Call Features with TTS/STT (NEW!)
- **Speech-to-Text (STT)**: Local transcription using faster-whisper with Groq fallback
- **Text-to-Speech (TTS)**: Natural voice synthesis using Edge-TTS
- **Real-time Call Streaming**: pytgcalls integration for live voice chat participation
- **Voice Message Transcription**: Automatic transcription with timestamps
- **Contextual Responses**: AI responses based on call transcripts and chat history
- **Voice Output Streaming**: Direct audio streaming to voice calls or voice message fallback
- **FFmpeg Integration**: Seamless audio format conversions (PCM, Opus, WAV)
- **Multi-language Support**: Configurable languages for both TTS and STT
- **Smart Rate Limiting**: 30-second cooldown, probabilistic responses to avoid spam
- **Quiet Hours**: Configure times when bot should not participate
- **Admin Controls**: Full control over TTS/STT settings per chat

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

### 🛡️ Moderation & Admin
- **User Management**: Ban, mute, unmute users
- **Message Control**: Delete messages, lock/unlock chats
- **Feature Toggles**: Enable/disable AI, random chat, moderation per group
- **Daily Reminders**: Configurable exam countdown reminders

## Quick Start

### Prerequisites
- Python 3.10+
- Telegram Bot Token (from @BotFather)
- Telegram API ID and API Hash (from https://my.telegram.org)
- FFmpeg installed on system
- API Keys (see Configuration section)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai618-bot
```

2. Install FFmpeg (required for audio processing):
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (see Configuration)

5. Run the bot:
```bash
python main.py
```

## Configuration

### Required Environment Variables

Create a `.env` file with:

```bash
# Essential
BOT_TOKEN=your_telegram_bot_token
TARGET_CHAT_ID=-1001234567890  # Your group chat ID

# For pytgcalls (voice call participation)
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash

# AI Providers (at least one required)
CEREBRAS_API_KEY=your_cerebras_key
GROQ_API_KEY=your_groq_key
CHATANYWHERE_API_KEY=your_chatanywhere_key

# TTS/STT Configuration (optional)
WHISPER_MODEL_SIZE=base  # Options: tiny, base, small, medium, large
EDGE_TTS_VOICE=en-US-AriaNeural  # Edge-TTS voice name
EDGE_TTS_RATE=+0%  # Speech rate: -50% to +100%
FFMPEG_PATH=ffmpeg  # Path to FFmpeg binary

# For voice transcription fallback (optional)
GROQ_API_KEY=your_groq_key  # Used as STT fallback if local whisper fails

# For legacy voice responses (optional, Edge-TTS is now primary)
REPLICATE_API_KEY=your_replicate_key

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
- `config.json`: Non-sensitive settings (toggles, quiet hours, etc.)
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

### Voice & Call Features

```
# Call Control Commands
/joincall           - Manually join a voice chat (Admin)
/leavecall          - Manually leave a voice chat (Admin)
/callinfo           - Show detailed call state and framework status

# Call Configuration
/audio              - Toggle voice responses (Admin)
/callon             - Enable proactive call participation (Admin)
/calloff            - Disable proactive calls (Admin)
/callstatus         - Check call feature status (Admin)
/callquiet HH:MM HH:MM  - Set quiet hours (Admin)
/callconfig [num]   - Set min participants (Admin)

# TTS (Text-to-Speech) Commands
/ttson              - Enable TTS for this chat (Admin)
/ttsoff             - Disable TTS (Admin)
/ttsconfig [voice] [rate]  - Configure TTS voice and rate (Admin)
/ttsstatus          - Check TTS status

# STT (Speech-to-Text) Commands
/stton              - Enable STT for this chat (Admin)
/sttoff             - Disable STT (Admin)
/sttconfig [lang]   - Configure STT language (Admin)
/sttstatus          - Check STT status and model info
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

## Voice Call Features with TTS/STT

The bot can participate in group calls with real-time speech recognition and voice synthesis using the integrated **pytgcalls + Telethon call framework**. See [PROACTIVE_CALLS.md](PROACTIVE_CALLS.md) and [TTS_STT_GUIDE.md](TTS_STT_GUIDE.md) for detailed documentation.

### Call Framework Features:
- 📞 **Join/Leave Voice Chats**: Manual and automatic call participation
- 🔄 **Lifecycle Management**: Startup/shutdown hooks for graceful initialization and cleanup
- 🎙️ **Audio Stream Management**: Playback queue, volume controls, and audio frame capture
- 🔊 **Real-time Audio Streaming**: Direct TTS audio streaming to voice calls via pytgcalls
- 📥 **Incoming Audio Capture**: Buffer and process audio frames for STT
- 🔁 **Reconnection Logic**: Automatic retries with flood wait handling
- 📊 **Call State Tracking**: Per-chat state management (joined/left/idle)
- 🛡️ **Error Handling**: Graceful error recovery with retry logic and logging

### TTS/STT Features:
- 🎙️ **Local STT**: Fast transcription using faster-whisper (CPU/GPU) with Groq fallback
- 🔊 **Edge-TTS**: Natural voice synthesis with 100+ voices in multiple languages
- 🎵 **pytgcalls Integration**: Direct audio streaming to voice calls
- 🔄 **FFmpeg Processing**: Seamless audio format conversions (PCM, Opus, WAV)
- 🧠 **Context Awareness**: Merges call transcripts with chat history
- 💬 **Smart Responses**: Streamed audio or voice message fallback
- ⏰ **Quiet Hours**: Configurable do-not-disturb periods
- 🛡️ **Rate Limiting**: Built-in cooldowns prevent spam
- 📊 **Status Monitoring**: Track transcription quality, latency, and errors
- 🌐 **Multi-language**: Configurable languages for both TTS and STT

### Quick Setup:
```bash
# 1. Manually join a voice chat
/joincall

# 2. Check call framework status
/callinfo

# 3. Enable STT for voice message transcription
/stton

# 4. Configure STT language (optional)
/sttconfig en

# 5. Enable TTS for voice responses
/ttson

# 6. Configure TTS voice and rate (optional)
/ttsconfig en-US-AriaNeural +10%

# 7. Enable proactive call participation (optional)
/callon

# 8. Set quiet hours (optional)
/callquiet 22:00 08:00

# 9. Check status
/sttstatus
/ttsstatus
/callstatus

# 10. Leave the call when done
/leavecall
```

## Architecture

### Core Components
- **main.py**: Monolithic orchestrator (2400+ lines)
- **keep_alive.py**: Flask server for uptime monitoring
- **Configuration**: JSON-based persistence

### AI Provider Chain
1. **Primary**: Cerebras (qwen-3-235b-a22b-instruct-2507)
2. **Fallback 1**: Groq (openai/gpt-oss-120b)
3. **Fallback 2**: ChatAnywhere (gpt-4o-mini)

### Voice Processing
- **STT Primary**: faster-whisper (local, configurable model size)
- **STT Fallback**: Groq Whisper API (whisper-large-v3)
- **TTS Primary**: Edge-TTS (100+ voices, free)
- **TTS Legacy**: Replicate minimax/speech-02-hd (optional)
- **Audio Processing**: FFmpeg for format conversions
- **Call Streaming**: pytgcalls for real-time audio

### Vision Models
- **Primary**: TypeGPT Fast (gemini-2.5-pro)
- **Fallback**: OpenRouter (moonshotai/kimi-vl-a3b-thinking:free)

## Dependencies

Core libraries:
- `python-telegram-bot[job-queue]` - Telegram Bot API
- `telethon` - Userbot support for pytgcalls
- `pytgcalls` - Voice call participation and streaming
- `edge-tts` - Text-to-speech synthesis
- `faster-whisper` - Local speech-to-text transcription
- `soundfile` - Audio file handling
- `numpy` - Audio processing
- `ffmpeg-python` - Audio format conversions
- `httpx` - Async HTTP client
- `cerebras-cloud-sdk` - Cerebras AI
- `groq` - Groq API (LLM + Whisper fallback)
- `openai` - OpenAI-compatible clients
- `replicate` - Legacy TTS/video generation
- `rdkit` - Chemistry structures
- `Pillow` - Image processing
- `pydub` - Audio processing
- `BeautifulSoup4` - Web scraping
- `telegraph` - Long response publishing
- `emoji` - Emoji handling
- `pytz` - Timezone support

## Safety & Privacy

### Rate Limiting
- **Call Responses**: 30s cooldown between responses
- **Probabilistic Engagement**: 30% response chance
- **Error Tracking**: Auto-warn after 5 failures

### Data Retention
- **Chat History**: Last 30 messages (in-memory)
- **Call Transcripts**: Last 20 voice messages (in-memory)
- **Temporary Files**: Audio files deleted immediately after processing
- **Persistent Storage**: Only config, memory, and gossip JSON files

### User Control
- Admins can enable/disable all features per chat
- Quiet hours prevent unwanted activity
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
├── PROACTIVE_CALLS.md    # Call feature docs
├── CHANGES_SUMMARY.md    # Change log
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

### Voice Features Not Working
1. Verify `GROQ_API_KEY` is set (for STT)
2. Check proactive calls are enabled: `/callstatus`
3. Ensure you're in active hours (not in quiet period)
4. Send clear voice messages (avoid background noise)
5. Check Groq API quota/limits

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
- Voice processing by Groq Whisper and Replicate
- Image generation by various APIs

## Support

For issues, feature requests, or questions:
- Check [PROACTIVE_CALLS.md](PROACTIVE_CALLS.md) for call features
- Check [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) for recent updates
- Review logs for error messages
- Test with minimal configuration first

---

**Version**: 2.0.0
**Last Updated**: 2024
**Status**: Production Ready
