# Call Framework Integration Guide

## Overview

This bot now includes a comprehensive real-time voice/video call framework powered by **pytgcalls** and **Telethon**, enabling the userbot to join group calls, manage audio streams, and process voice communication.

## Features

### Core Capabilities
- 📞 **Join/Leave Voice Chats**: Manual commands and auto-join based on configuration
- 🔄 **Lifecycle Management**: Automatic startup/shutdown hooks for graceful initialization
- 🎙️ **Audio Stream Management**: Playback queues, volume controls, and stream changes
- 🔊 **TTS Audio Streaming**: Stream synthesized speech directly to voice calls
- 📥 **Audio Frame Capture**: Buffer incoming audio for speech-to-text processing
- 🔁 **Reconnection Logic**: Automatic retries with exponential backoff and flood wait handling
- 📊 **Call State Tracking**: Per-chat state management (idle/joined/left)
- 🛡️ **Error Handling**: Comprehensive error recovery with logging

## Architecture

### Components

1. **Telethon Client**: Core MTProto client for Telegram API access
2. **PyTgCalls**: Voice/video call library built on top of Telegram's group calls
3. **Audio Buffers**: Per-chat deques for incoming audio frame storage
4. **TTS Queues**: Async queues for managing outgoing audio streams
5. **Call State Manager**: Track call status, participants, transcripts, and errors

### State Management

Each chat has a call state dictionary:
```python
{
    "state": "idle/joined/left",
    "participants": [],
    "transcript": deque(maxlen=20),
    "last_response_time": datetime,
    "error_count": 0,
    "join_time": datetime,
    "auto_joined": bool
}
```

## Installation

### Dependencies

The following packages are required (already in `requirements.txt`):
- `telethon` - Telegram client library
- `tgcrypto` - Encryption acceleration for Telethon
- `pytgcalls` - Voice call integration
- `pydub` - Audio manipulation
- `ffmpeg-python` - FFmpeg wrapper
- `edge-tts` - Text-to-speech
- `faster-whisper` - Speech-to-text
- `soundfile` - Audio I/O
- `numpy` - Numerical operations

### System Requirements

**FFmpeg must be installed** on your system:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Configuration

Add these environment variables:
```bash
# Required for pytgcalls/Telethon
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash

# Optional: FFmpeg path if not in PATH
FFMPEG_PATH=/usr/bin/ffmpeg
```

Get your `API_ID` and `API_HASH` from https://my.telegram.org/apps

## Usage

### Manual Call Control

#### Join a Voice Chat
```
/joincall
```
- Admin only
- Checks if API credentials are configured
- Verifies a voice chat is active
- Initializes pytgcalls and joins with silent audio stream
- Returns status confirmation

#### Leave a Voice Chat
```
/leavecall
```
- Admin only
- Gracefully leaves the current voice chat
- Cleans up buffers and state
- Confirms successful departure

#### Check Call Status
```
/callinfo
```
- Shows detailed framework status
- Call state (idle/joined/left)
- pytgcalls instance status
- Telethon client connectivity
- Transcript buffer count
- Error count and call duration

### Automatic Call Participation

Enable auto-join based on configuration:
```
/callon              # Enable proactive calls
/callconfig 3        # Require 3+ participants
/callquiet 22:00 08:00  # Quiet hours
```

The bot will automatically join calls when:
- Proactive calls are enabled
- Participant count meets minimum
- Not in quiet hours
- No recent errors

## API Reference

### Core Functions

#### `initialize_telethon_client()`
Initializes the global Telethon client for pytgcalls.
- **Returns**: `TelegramClient` instance or `None`
- **Called**: Once on bot startup (post_init hook)
- **Handles**: Connection, authentication with bot token

#### `shutdown_telethon_client()`
Gracefully shuts down the Telethon client.
- **Called**: On bot shutdown (post_shutdown hook)
- **Handles**: Leaving all active calls, disconnecting client

#### `initialize_pytgcalls(chat_id: int)`
Initializes a pytgcalls instance for a specific chat.
- **Parameters**: `chat_id` - Telegram chat ID
- **Returns**: `PyTgCalls` instance or `None`
- **Caches**: Reuses existing instance if available

#### `join_voice_chat(chat_id: int, auto_join: bool = False)`
Joins a voice chat in the specified chat.
- **Parameters**:
  - `chat_id` - Telegram chat ID
  - `auto_join` - Whether this is an auto-join (for logging)
- **Returns**: `bool` - Success status
- **Side Effects**:
  - Initializes call state
  - Creates audio buffers and TTS queues
  - Streams silent audio initially

#### `leave_voice_chat(chat_id: int)`
Leaves a voice chat in the specified chat.
- **Parameters**: `chat_id` - Telegram chat ID
- **Returns**: `bool` - Success status
- **Side Effects**:
  - Updates call state to "left"
  - Clears transcript buffer
  - Empties audio buffers and TTS queues

#### `get_call_state(chat_id: int)`
Gets the current call state for a chat.
- **Parameters**: `chat_id` - Telegram chat ID
- **Returns**: `dict` - Call state dictionary

#### `is_in_call(chat_id: int)`
Checks if the bot is currently in a voice chat.
- **Parameters**: `chat_id` - Telegram chat ID
- **Returns**: `bool` - True if in call

### Audio Stream Functions

#### `stream_tts_to_call(chat_id: int, text: str, voice: str, rate: str)`
Streams TTS audio to a voice call.
- **Parameters**:
  - `chat_id` - Telegram chat ID
  - `text` - Text to synthesize
  - `voice` - Edge-TTS voice name (optional)
  - `rate` - Speech rate (optional)
- **Returns**: `bool` - Success status
- **Process**:
  1. Generate TTS audio with Edge-TTS
  2. Convert to PCM 48kHz stereo
  3. Stream via pytgcalls change_stream()

#### `play_audio_to_call(chat_id: int, audio_path: str)`
Plays an audio file to a voice call.
- **Parameters**:
  - `chat_id` - Telegram chat ID
  - `audio_path` - Path to audio file
- **Returns**: `bool` - Success status
- **Process**:
  1. Convert audio to PCM format
  2. Stream via pytgcalls

#### `capture_call_audio(chat_id: int, duration: int = 5)`
Captures audio frames from a voice call.
- **Parameters**:
  - `chat_id` - Telegram chat ID
  - `duration` - Seconds to capture (default: 5)
- **Returns**: `bytes` - Raw audio data or `None`
- **Use Case**: Feed to STT for transcription

## Error Handling

### Retry Logic

The framework includes automatic retry logic:
- **Connection Failures**: Retry with exponential backoff
- **Flood Wait**: Respect Telegram rate limits
- **Access Errors**: Log and disable feature for chat

### Error Tracking

Each chat tracks:
- `error_count` - Consecutive failures
- Warnings after 5 consecutive errors
- Automatic feature suggestions on repeated failures

### Logging

All operations are logged with:
- ✅ Success indicators
- ⚠️ Warnings for recoverable issues
- ❌ Errors with stack traces
- 📊 State transitions

## Integration with Bot Features

### TTS/STT Integration

When both TTS and call framework are enabled:
1. Voice messages are transcribed
2. AI generates contextual response
3. Response is synthesized to audio
4. Audio is streamed to call (or sent as voice message if not in call)

### Proactive Call Feature

The existing proactive call feature now leverages the framework:
- Auto-join when conditions are met
- Transcript management for context
- Rate limiting and quiet hours respected

### Call State Coordination

Other features can check call state:
```python
if await is_in_call(chat_id):
    # In call - stream audio
    await stream_tts_to_call(chat_id, response)
else:
    # Not in call - send voice message
    await send_voice_message(chat_id, response)
```

## Best Practices

### Resource Management
- Initialize once on startup
- Reuse pytgcalls instances per chat
- Clean up temporary audio files
- Clear buffers on call end

### Error Recovery
- Log all errors with context
- Track error counts per chat
- Provide user feedback on failures
- Gracefully degrade to fallback modes

### Audio Quality
- Use 48kHz sample rate for calls
- Stereo audio for better quality
- Proper format conversion with FFmpeg
- Async processing to avoid blocking

### Security
- Store API_ID and API_HASH securely
- Session files contain auth tokens - keep private
- Validate admin permissions for all commands
- Rate limit call operations

## Troubleshooting

### Common Issues

#### "API_ID and API_HASH required"
**Solution**: Set environment variables from https://my.telegram.org/apps

#### "Failed to initialize Telethon client"
**Causes**:
- Invalid API credentials
- Network connectivity issues
- Bot token expired

**Solution**:
- Verify API_ID and API_HASH
- Check internet connection
- Regenerate bot token if needed

#### "Cannot join call: pytgcalls initialization failed"
**Causes**:
- Telethon client not initialized
- No active voice chat in group
- Insufficient permissions

**Solution**:
- Check `/callinfo` status
- Start a voice chat in the group
- Ensure bot is admin with voice chat permissions

#### "Failed to stream TTS to call"
**Causes**:
- Not currently in call
- Audio generation failed
- FFmpeg conversion error

**Solution**:
- Verify `/callinfo` shows "In Call: ✅ Yes"
- Check FFmpeg installation
- Review logs for specific error

#### "FFmpeg not found"
**Solution**:
```bash
# Check if FFmpeg is installed
ffmpeg -version

# If not, install it
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS
```

### Debug Commands

```bash
# Check framework status
/callinfo

# Check TTS/STT status
/ttsstatus
/sttstatus

# Check proactive call config
/callstatus

# Test joining manually
/joincall
```

### Logs

Important log messages to watch for:
```
✅ Telethon client started successfully
✅ pytgcalls instance created for chat X
✅ Successfully joined voice chat in chat X
✅ TTS audio streamed to call in chat X
```

Error patterns to investigate:
```
❌ Failed to initialize Telethon client
❌ Cannot join call: pytgcalls initialization failed
⚠️ Cannot stream TTS: not in voice chat
```

## Performance Considerations

### Resource Usage
- **Telethon**: ~10-20 MB RAM per client
- **pytgcalls**: ~5-10 MB RAM per call
- **Audio Buffers**: ~1-5 MB per chat
- **TTS Queue**: Minimal (<1 MB)

### Latency
- **Join Call**: 1-3 seconds
- **Leave Call**: <1 second
- **Stream Audio**: 2-4 seconds (includes TTS generation and conversion)
- **Capture Audio**: Real-time with 100ms buffer

### Optimization Tips
1. Keep pytgcalls instances alive for active chats
2. Reuse Telethon client globally
3. Async operations prevent blocking
4. Clear old audio buffers periodically

## Future Enhancements

Potential improvements:
- [ ] Video streaming support
- [ ] Multi-speaker audio mixing
- [ ] Real-time audio effects (noise suppression, echo cancellation)
- [ ] Call recording and export
- [ ] Live transcription display
- [ ] Sentiment analysis of call participants
- [ ] Auto-generated call summaries
- [ ] Speaker diarization (who said what)
- [ ] Background music playback
- [ ] Advanced queue management (priority, scheduling)

## Support

For issues:
1. Check `/callinfo` for current status
2. Review logs for error messages
3. Verify all prerequisites are met
4. Test with simple operations first (`/joincall`, `/leavecall`)
5. Consult [TTS_STT_GUIDE.md](TTS_STT_GUIDE.md) for audio specifics

## License

Same as the main bot project.
