# Audio Generation Guide - Edge TTS Implementation

## Overview

This bot uses Microsoft's Edge TTS (Text-to-Speech) service for free, unlimited audio generation. This guide explains how the implementation works and how to maintain it.

## Architecture

### Key Components

1. **`generate_audio_from_text()`** - Core audio generation function
2. **`send_final_response()`** - Handles audio mode and sending
3. **`toggle_audio_mode_handler()`** - Command handler for /audio

## Audio Generation Flow

```
User sends /ai query
    ↓
AI generates text response
    ↓
Is audio mode enabled for this chat?
    ↓ Yes
Send "🎤 Generating audio..." message
    ↓
generate_audio_from_text(text, voice)
    ↓
Create temp file: /tmp/tts_temp_{id}_{random}.mp3
    ↓
edge_tts.Communicate(text, voice)
    ↓
await communicate.save(temp_file)
    ↓
Verify file exists and has content
    ↓
Read audio bytes
    ↓
Clean up temp file
    ↓
Send via send_voice() to Telegram
```

## Code Pattern

### Correct Usage (ALWAYS USE THIS PATTERN)

```python
import edge_tts
import os
import random

async def generate_audio_from_text(text: str, voice: str = "en-US-GuyNeural") -> bytes | None:
    """Generate audio from text using Edge TTS."""
    
    # 1. Clean the text
    cleaned_text = re.sub(r'[*_`]', '', text)
    if not cleaned_text.strip():
        return None
    
    # 2. Create temp file path (USE /tmp/)
    temp_file = f"/tmp/tts_temp_{id(text)}_{random.randint(1000, 9999)}.mp3"
    
    try:
        # 3. Generate audio with Edge TTS
        communicate = edge_tts.Communicate(cleaned_text, voice)
        await communicate.save(temp_file)  # MUST await this!
        
        # 4. VERIFY file was created
        if not os.path.exists(temp_file):
            logger.error(f"Temp file was not created: {temp_file}")
            return None
        
        # 5. VERIFY file has content
        file_size = os.path.getsize(temp_file)
        if file_size == 0:
            logger.error("Generated audio file is empty")
            os.remove(temp_file)
            return None
        
        # 6. Read the audio bytes
        with open(temp_file, 'rb') as f:
            audio_bytes = f.read()
        
        # 7. Clean up temp file
        try:
            os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to clean up: {e}")
        
        return audio_bytes
        
    except Exception as e:
        logger.error(f"Failed to generate audio: {e}", exc_info=True)
        # Clean up on error
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        return None
```

## Common Issues and Solutions

### Issue: "No audio was received"
**Cause**: Temp file not created or empty
**Solution**: ✅ Already fixed - we verify file existence and size

### Issue: 401 Authentication Error
**Cause**: Microsoft rotated Edge TTS API keys in the library
**Solution**: 
```bash
pip install --upgrade edge-tts
```
Or wait for library maintainers to update keys

### Issue: Permission Denied
**Cause**: Cannot write to temp directory
**Solution**: ✅ Already fixed - using `/tmp/` which has universal write permissions

### Issue: File Already Exists
**Cause**: Temp file name collision
**Solution**: ✅ Already fixed - using `random.randint()` in filename

## Configuration

### Available Voices

```python
AVAILABLE_TTS_VOICES = {
    "guy": "en-US-GuyNeural",      # Deep male (default)
    "davis": "en-US-DavisNeural",  # Deep male
    "tony": "en-US-TonyNeural",    # Male
    "jason": "en-US-JasonNeural",  # Male
    "jenny": "en-US-JennyNeural",  # Female
    "aria": "en-US-AriaNeural",    # Female
    "sara": "en-US-SaraNeural",    # Female
    "brian": "en-GB-RyanNeural",   # British male
    "sonia": "en-GB-SoniaNeural",  # British female
}
```

### Adding New Voices

1. Find voice names at: https://speech.microsoft.com/portal/voicegallery
2. Add to `AVAILABLE_TTS_VOICES` dict in main.py
3. Update help text if needed

## User Commands

```
/audio              # Toggle audio mode on/off
/audio list         # Show all available voices
/audio guy          # Set voice to "guy" (en-US-GuyNeural)
/audio jenny        # Set voice to "jenny" (en-US-JennyNeural)
```

## Logging

The implementation logs at multiple stages:

- **INFO**: Normal operations (generation start, file created, success)
- **WARNING**: Non-critical issues (cleanup failures, empty text)
- **ERROR**: Critical failures (file not created, generation failed)
- **DEBUG**: Detailed information (cleanup success)

Example log output:
```
INFO - Generating audio with Edge TTS using voice: en-US-GuyNeural
INFO - Text length: 156 characters
INFO - Temp file: /tmp/tts_temp_140234567890123_5432.mp3
INFO - Audio file created: 45632 bytes
INFO - Successfully generated audio: 45632 bytes
INFO - Audio mode enabled for chat -1001234567890, using voice: en-US-GuyNeural
INFO - Audio generated successfully, sending to Telegram (45632 bytes)
INFO - Audio sent successfully to Telegram
```

## Error Handling

The implementation handles these specific errors:

1. **FileNotFoundError**: Temp file wasn't created
2. **PermissionError**: No write access to temp directory
3. **Exception**: Generic catch-all with full traceback

All errors result in:
- Detailed error logging
- Cleanup of temp files (if they exist)
- Graceful fallback to text response
- User-friendly error message

## Testing

To test Edge TTS locally:

```bash
python test_edge_tts.py
```

This will:
1. Generate a test audio file
2. Verify file creation and size
3. Test multiple voices
4. Clean up after testing

## Maintenance

### Regular Updates
```bash
# Update edge-tts library (recommended monthly)
pip install --upgrade edge-tts
```

### Monitor Logs
Watch for these error patterns:
- 401 errors → Update edge-tts library
- Permission errors → Check file system permissions
- Empty files → Possible network issues

### Debugging Checklist

If audio generation fails:

1. ✅ Check logs for specific error messages
2. ✅ Verify temp file path `/tmp/` is writable
3. ✅ Check edge-tts library version: `pip show edge-tts`
4. ✅ Test network connectivity to Microsoft services
5. ✅ Update edge-tts: `pip install --upgrade edge-tts`
6. ✅ Check GitHub issues: https://github.com/rany2/edge-tts/issues

## Best Practices

### DO ✅
- Always use `/tmp/` for temp files
- Always verify file existence and size
- Always clean up temp files (even on error)
- Always use specific exception handling
- Always log with appropriate level
- Always await `communicate.save()`
- Always provide fallback to text

### DON'T ❌
- Don't use current directory for temp files
- Don't skip file verification
- Don't ignore cleanup errors silently
- Don't use generic `except: pass`
- Don't block async operations
- Don't forget to await async calls
- Don't fail without user feedback

## Dependencies

```
edge-tts>=7.2.3    # Microsoft Edge TTS
aiohttp            # Async HTTP (edge-tts dependency)
```

## References

- Edge TTS GitHub: https://github.com/rany2/edge-tts
- Microsoft Voice Gallery: https://speech.microsoft.com/portal/voicegallery
- Telegram Bot API (send_voice): https://core.telegram.org/bots/api#sendvoice
