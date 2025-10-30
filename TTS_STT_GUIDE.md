# TTS and STT Integration Guide

## Overview

This bot now supports bidirectional audio processing for voice calls:
- **Speech-to-Text (STT)**: Transcribe voice messages using faster-whisper (local) with Groq API fallback
- **Text-to-Speech (TTS)**: Synthesize responses using Edge-TTS
- **pytgcalls Integration**: Stream audio directly to voice calls

## Architecture

### Components

1. **faster-whisper**: Local transcription engine
   - Configurable model size (tiny, base, small, medium, large)
   - CPU optimized with int8 compute type
   - VAD (Voice Activity Detection) for better accuracy
   - Provides timestamps and segment information

2. **Edge-TTS**: Text-to-speech synthesis
   - 100+ voices across multiple languages
   - Free and fast
   - Configurable speech rate (-50% to +100%)
   - Natural-sounding voices

3. **pytgcalls**: Voice call participation
   - Real-time audio streaming
   - Integration with Telethon for bot session
   - Supports PCM and Opus audio formats

4. **FFmpeg**: Audio format conversion
   - Converts between formats (MP3, WAV, OGG, PCM)
   - Resampling and channel configuration
   - Async subprocess execution

### Audio Pipeline

#### Incoming Audio (STT):
```
Voice Message → Download → OGG File → FFmpeg → WAV (16kHz mono) 
→ faster-whisper → Transcript + Timestamps → Bot Logic
```

If faster-whisper fails, fallback:
```
Voice Message → Download → OGG File → Groq Whisper API → Transcript
```

#### Outgoing Audio (TTS):
```
Text Response → Edge-TTS → MP3 File → FFmpeg → PCM (48kHz stereo) 
→ pytgcalls → Stream to Call
```

If streaming fails, fallback:
```
Text Response → Edge-TTS → MP3 → Voice Message in Chat
```

## Configuration

### Environment Variables

```bash
# Required for pytgcalls
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash

# TTS Configuration (optional)
EDGE_TTS_VOICE=en-US-AriaNeural  # Default voice
EDGE_TTS_RATE=+0%                # Speech rate adjustment

# STT Configuration (optional)
WHISPER_MODEL_SIZE=base          # tiny, base, small, medium, large

# FFmpeg Configuration (optional)
FFMPEG_PATH=ffmpeg               # Path to FFmpeg binary

# Fallback STT (optional)
GROQ_API_KEY=your_groq_key       # Used if faster-whisper fails
```

### Per-Chat Configuration

All settings are configurable per chat using commands:

#### TTS Settings:
- **Enable/Disable**: `/ttson` or `/ttsoff`
- **Voice**: `/ttsconfig en-US-AriaNeural +10%`
- **Status**: `/ttsstatus`

#### STT Settings:
- **Enable/Disable**: `/stton` or `/sttoff`
- **Language**: `/sttconfig en`
- **Status**: `/sttstatus`

## Commands Reference

### TTS Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/ttson` | Enable TTS for this chat | `/ttson` |
| `/ttsoff` | Disable TTS | `/ttsoff` |
| `/ttsconfig` | Set voice and rate | `/ttsconfig en-US-AriaNeural +10%` |
| `/ttsstatus` | Check TTS status | `/ttsstatus` |

### STT Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/stton` | Enable STT for this chat | `/stton` |
| `/sttoff` | Disable STT | `/sttoff` |
| `/sttconfig` | Set language | `/sttconfig es` |
| `/sttstatus` | Check STT status | `/sttstatus` |

## Usage Examples

### Basic Voice Message Transcription

1. Enable STT:
   ```
   /stton
   ```

2. Send a voice message to the group

3. Bot will transcribe it and respond if configured

### Voice Call Participation

1. Enable STT and TTS:
   ```
   /stton
   /ttson
   ```

2. Configure voice (optional):
   ```
   /ttsconfig en-GB-SoniaNeural +5%
   ```

3. Enable proactive calls:
   ```
   /callon
   ```

4. Start a voice call and send voice messages
5. Bot will transcribe messages and respond with audio

### Multi-language Support

For Spanish transcription and response:
```
/sttconfig es
/ttsconfig es-ES-ElviraNeural +0%
/stton
/ttson
```

## Available Voices

### English
- `en-US-AriaNeural` (Female, friendly)
- `en-US-GuyNeural` (Male, casual)
- `en-US-JennyNeural` (Female, professional)
- `en-GB-SoniaNeural` (Female, British)
- `en-GB-RyanNeural` (Male, British)
- `en-AU-NatashaNeural` (Female, Australian)

### Other Languages
- Spanish: `es-ES-ElviraNeural`, `es-MX-DaliaNeural`
- French: `fr-FR-DeniseNeural`, `fr-CA-SylvieNeural`
- German: `de-DE-KatjaNeural`, `de-AT-IngridNeural`
- Italian: `it-IT-ElsaNeural`, `it-IT-DiegoNeural`
- Portuguese: `pt-BR-FranciscaNeural`, `pt-PT-RaquelNeural`
- Russian: `ru-RU-SvetlanaNeural`, `ru-RU-DmitryNeural`
- Chinese: `zh-CN-XiaoxiaoNeural`, `zh-TW-HsiaoChenNeural`
- Japanese: `ja-JP-NanamiNeural`, `ja-JP-KeitaNeural`
- Korean: `ko-KR-SunHiNeural`, `ko-KR-InJoonNeural`

Full list: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts

## Supported Languages (STT)

faster-whisper supports 99+ languages. Common ones:
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ru` - Russian
- `zh` - Chinese
- `ja` - Japanese
- `ko` - Korean
- `ar` - Arabic
- `hi` - Hindi

## Performance Considerations

### Whisper Model Sizes

| Model | Size | Speed | Accuracy | Recommended For |
|-------|------|-------|----------|----------------|
| tiny | ~39 MB | Fastest | Good | Low-resource systems |
| base | ~74 MB | Fast | Better | Default choice |
| small | ~244 MB | Moderate | Good | Better accuracy needed |
| medium | ~769 MB | Slow | Very Good | High accuracy needed |
| large | ~1550 MB | Slowest | Best | Maximum accuracy |

**Default**: `base` - Good balance of speed and accuracy

### Resource Usage

- **STT**: CPU intensive, ~1-5 seconds per voice message (depends on model)
- **TTS**: Fast, ~0.5-2 seconds per response
- **FFmpeg**: Minimal overhead, ~0.1-0.3 seconds per conversion
- **pytgcalls**: Requires Telethon session, minimal memory

### Optimization Tips

1. **Use smaller models for faster transcription**: `WHISPER_MODEL_SIZE=tiny`
2. **Adjust TTS rate for faster speech**: `/ttsconfig en-US-GuyNeural +50%`
3. **Enable only when needed**: Turn off TTS/STT when not actively using
4. **Monitor with status commands**: `/sttstatus` shows model load status

## Error Handling

### Common Issues

1. **FFmpeg not found**
   - Solution: Install FFmpeg (`apt install ffmpeg` or download from ffmpeg.org)
   - Configure path: `FFMPEG_PATH=/path/to/ffmpeg`

2. **Whisper model fails to load**
   - Check available memory
   - Try smaller model: `WHISPER_MODEL_SIZE=tiny`
   - Falls back to Groq API automatically

3. **TTS audio not streaming**
   - Bot falls back to sending voice messages
   - Check API_ID and API_HASH are set correctly
   - Verify Telethon session is initialized

4. **Transcription is slow**
   - Use smaller Whisper model
   - Consider using only Groq fallback
   - Check CPU resources

### Logging

All TTS/STT operations are logged with:
- Operation type (TTS generation, STT transcription, etc.)
- Latency measurements
- Error messages with stack traces
- Configuration details

Check logs for troubleshooting:
```bash
# Look for TTS/STT related logs
grep -i "tts\|stt\|whisper\|edge-tts" bot.log
```

## Integration with Bot Features

### Call Transcription
- Voice messages in calls are automatically transcribed
- Transcripts are stored with timestamps
- Added to chat history for context-aware responses

### AI Response Generation
- Bot decides probabilistically whether to respond (30% chance)
- 30-second cooldown between responses
- Responses are based on:
  - Call transcript
  - Recent chat history
  - Gossip/memory data

### Quiet Hours
- TTS/STT respects configured quiet hours
- Use `/callquiet` to set do-not-disturb periods

### Rate Limiting
- Built-in cooldowns prevent spam
- Error tracking for transcription failures
- Automatic fallback to text if audio fails repeatedly

## Development Notes

### Adding New Voices

Edge-TTS uses Microsoft Azure voices. To use a new voice:
1. Find the voice name from the [Microsoft documentation](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)
2. Use `/ttsconfig [voice_name] [rate]`

### Custom FFmpeg Parameters

To modify audio quality, edit `convert_audio_format()` in main.py:
```python
# Example: Higher quality audio
sample_rate=48000,  # 48kHz
channels=2,         # Stereo
```

### Extending pytgcalls Integration

The `stream_tts_to_call()` function handles call streaming. To modify:
1. Adjust audio format parameters
2. Change streaming quality
3. Add video streaming support

## Security Considerations

1. **API Credentials**: Store API_ID and API_HASH securely in environment variables
2. **Session Files**: `.session` files contain authentication - keep them private
3. **Audio Files**: Temporary files are cleaned up automatically
4. **Rate Limiting**: Built-in to prevent abuse

## Troubleshooting Checklist

- [ ] FFmpeg installed and in PATH
- [ ] API_ID and API_HASH set correctly
- [ ] Sufficient disk space for audio files
- [ ] Adequate memory for Whisper model
- [ ] Bot has admin permissions in group
- [ ] TTS/STT enabled for the chat
- [ ] No firewall blocking audio streaming

## Future Enhancements

Potential improvements:
- [ ] GPU acceleration for faster-whisper
- [ ] Speaker diarization (who said what)
- [ ] Real-time streaming transcription
- [ ] Voice cloning/customization
- [ ] Noise suppression
- [ ] Echo cancellation
- [ ] Multi-speaker support

## Support

For issues or questions:
1. Check `/sttstatus` and `/ttsstatus` for current configuration
2. Review logs for error messages
3. Try fallback modes (disable local whisper, use Groq only)
4. Verify FFmpeg and dependencies are installed
5. Test with simple voice messages first

## License

Same as the main bot project.
