# TTS Speak Mode Implementation

## Overview
This implementation adds advanced Text-to-Speech (TTS) functionality to the chatbot with a new "Speak Mode" feature that allows users to toggle between text and audio-only responses.

## Features Implemented

### 1. TTS API Integration (`modules/media.py`)
- **New Function**: `generate_tts_api_audio()`
  - Connects to an external TTS API (e.g., OpenAI-compatible proxy)
  - Supports configurable voices and emotion parameters
  - Returns audio bytes for direct transmission to Telegram
  - Includes error handling and logging

- **Configuration**:
  - `TTS_API_URL`: The endpoint of your TTS API
  - `TTS_API_KEY`: Bearer token for API authentication
  - Both configured via environment variables

- **Supported Voices**: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse

### 2. Voice Selection Command (`/ttsvoice`)
- Allows users to select their preferred TTS voice
- Usage: `/ttsvoice <voice_name>`
- Shows available voices if no argument provided
- Voice preference is stored per-user and persists during bot session

### 3. Speak Mode Toggle (`/speak`)
- Toggles audio-only response mode on/off per user
- When enabled: All AI responses are sent as audio messages (no text)
- When disabled: Responses revert to text-only mode
- Usage: Simply type `/speak` to toggle
- State is tracked per-user in `FeatureManager.speak_mode_enabled` dictionary

### 4. Audio Response Helper (`send_audio_response()`)
- New async function in `modules/media.py`
- Generates TTS audio for AI responses
- Shows "🎤 Generating audio response..." status message
- Sends audio as Telegram audio message with title "AI Response"
- Falls back to text if audio generation fails
- Automatically deletes status message after completion

### 5. Integration with Main Handler
- Modified `master_text_handler()` in `main.py`
- Checks if user has Speak Mode enabled before sending response
- Routes to `send_audio_response()` for audio or `reply_text()` for text

### 6. Feature Manager Updates (`modules/features.py`)
- New method: `toggle_speak(update, context)`
  - Toggles speak mode for the requesting user
  - Sends confirmation message
- New method: `is_speak_mode_enabled(user_id)`
  - Helper to check if user has speak mode enabled
- Per-user speak mode state tracking

## Configuration

### Environment Variables Required
```
TTS_API_URL=https://your-tts-api-endpoint/v1/audio/speech
TTS_API_KEY=your-bearer-token
```

### Example TTS API Call
```python
POST https://your-tts-api-endpoint/v1/audio/speech
Headers:
  Authorization: Bearer your-api-key
  Content-Type: application/json

Payload:
{
  "model": "tts-1",
  "input": "The text to convert to speech",
  "voice": "ash",
  "prompt": "energetic, expressive, warm",
  "voice_metadata": {
    "emotion": "energetic",
    "intensity": 5,
    "pacing": "normal",
    "vocal_traits": "expressive, warm"
  }
}
```

## Usage Guide

### For Users

1. **Enable Speak Mode**:
   ```
   /speak
   ```
   Response: "🎤 Speak Mode is now **ON**. I will respond with audio messages only."

2. **Select a Voice**:
   ```
   /ttsvoice ash
   ```
   Response: "🎤 TTS voice set to: **Ash**"

3. **View Available Voices**:
   ```
   /ttsvoice
   ```
   Shows list of all available voices

4. **Disable Speak Mode**:
   ```
   /speak
   ```
   Response: "🎤 Speak Mode is now **OFF**. I will respond with text messages."

### For Developers

The speak mode state is maintained in:
- `feature_manager.speak_mode_enabled[user_id]`: boolean value (True/False)
- `media.user_tts_voices[user_id]`: selected voice name (default: "ash")

## Technical Details

### Audio Generation Flow
1. User sends message → AI generates response text
2. Check if `feature_manager.is_speak_mode_enabled(user_id)` returns True
3. If True: Call `media.send_audio_response(response_text, update, context)`
4. Generate audio using `generate_tts_api_audio(text, voice)`
5. Send as Telegram audio message with title "AI Response"
6. If generation fails: Fall back to text message

### Error Handling
- Missing API configuration: Logs warning and returns None
- API errors (non-200 status): Logs error and returns None
- Audio generation failure: Falls back to sending text response
- All exceptions caught and logged for debugging

## Files Modified

1. **`.env.example`**
   - Added `TTS_API_URL` and `TTS_API_KEY` configuration options

2. **`modules/media.py`**
   - Added `httpx` import for async HTTP requests
   - Added TTS configuration and voice list
   - New function: `generate_tts_api_audio(text, voice, emotion)`
   - New handler: `handle_tts_voice(update, context)`
   - New function: `send_audio_response(text, update, context)`

3. **`modules/features.py`**
   - Added `speak_mode_enabled` dictionary to FeatureManager
   - New method: `toggle_speak(update, context)`
   - New helper: `is_speak_mode_enabled(user_id)`

4. **`main.py`**
   - Registered `/speak` command handler
   - Registered `/ttsvoice` command handler
   - Modified response logic to check speak mode and route accordingly

5. **`README.md`**
   - Updated TTS features section
   - Added new commands documentation
   - Enhanced feature descriptions

## Dependencies

All required dependencies are already in `requirements.txt`:
- `httpx` (for async HTTP requests)
- `telegram` (already included)
- `python-telegram-bot[job-queue]` (already included)

## Future Enhancements

Possible improvements:
1. Persist user preferences to database
2. Add emotion/intensity controls per user
3. Support for different AI models
4. Batch audio generation for long responses
5. Audio caching for repeated phrases
6. Support for multiple languages
7. Admin toggle for TTS feature per chat

## Testing

To test the implementation:
1. Configure `TTS_API_URL` and `TTS_API_KEY` in environment
2. Run the bot: `python3 main.py`
3. Send `/speak` to enable speak mode
4. Send `/ttsvoice <voice>` to select a voice
5. Send a message that triggers AI response
6. Verify audio message is sent instead of text

## Support

If issues arise:
- Check that `TTS_API_URL` and `TTS_API_KEY` are properly set
- Verify TTS API is accessible and responding correctly
- Check bot logs for error messages
- Ensure bot has permission to send audio messages in the chat
