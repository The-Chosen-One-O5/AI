# Proactive Call Features - Documentation

## Overview

The bot now includes proactive call participation features that allow it to:
- Listen to voice messages during group calls
- Transcribe speech to text using AI (Groq Whisper)
- Generate contextual responses based on conversation flow
- Respond via text or voice (configurable)
- Respect rate limits, quiet hours, and safety constraints

## How It Works

### Voice Message Processing Flow

1. **Voice Message Detection**: When a voice message is sent in a group where proactive calls are enabled, the bot processes it automatically.

2. **Transcription**: The audio is transcribed using Groq's Whisper API (free and fast):
   - Supports multiple languages (default: English)
   - High accuracy for conversational speech
   - Handles background noise reasonably well

3. **Context Building**: The bot maintains:
   - Recent call transcript (last 20 voice messages)
   - Chat history (last 30 text messages)
   - Combined context for intelligent responses

4. **Response Generation**: 
   - AI analyzes the context and decides if a response is appropriate
   - Probabilistic response (30% chance) to avoid excessive interruption
   - Rate-limited (minimum 30 seconds between responses)
   - Respects quiet hours configuration

5. **Output**:
   - Text response (default)
   - Voice response (if audio mode is enabled with `/audio`)

## Admin Commands

### Enable/Disable Proactive Calls

```
/callon - Enable proactive call participation
/calloff - Disable proactive call participation
/callstatus - Check current configuration and status
```

### Configuration

```
/callconfig [min_participants]
```
Set the minimum number of participants required before the bot will engage.
- Default: 2 participants
- Example: `/callconfig 3` (bot waits for 3+ participants)

### Quiet Hours

```
/callquiet HH:MM HH:MM
```
Set time range when the bot should NOT participate in calls.
- Format: 24-hour time (IST timezone)
- Example: `/callquiet 22:00 08:00` (quiet from 10 PM to 8 AM)
- Supports overnight ranges

### Audio Mode Toggle

```
/audio
```
Toggle between text and voice responses. When enabled:
- Bot responses are sent as voice messages
- Uses Replicate's minimax/speech-02-hd TTS model
- Fallback to text if audio generation fails

## Safety Features

### Rate Limiting
- **Response Cooldown**: Minimum 30 seconds between bot responses
- **Probabilistic Engagement**: 30% chance to respond (prevents dominating conversation)
- **Error Tracking**: Monitors transcription failures and warns after 5 consecutive errors

### Fallback Behavior
- If speech is unclear or transcription fails, bot stays silent
- After multiple transcription errors, sends warning message
- Graceful degradation - text features continue working normally

### Flood Protection
- Rate limiting prevents spam
- Quiet hours prevent late-night disturbances
- Minimum participant threshold prevents unnecessary activation

## Configuration Structure

### Config File (`config.json`)

```json
{
  "proactive_call_config": {
    "CHAT_ID": {
      "enabled": true,
      "min_participants": 2
    }
  },
  "call_quiet_hours": {
    "CHAT_ID": {
      "start": "22:00",
      "end": "08:00"
    }
  },
  "audio_mode_config": {
    "CHAT_ID": true
  }
}
```

## Technical Details

### STT (Speech-to-Text)
- **Provider**: Groq Whisper API
- **Model**: whisper-large-v3
- **Format**: Accepts OGG/Opus (Telegram voice message format)
- **Language**: Configurable (default: English)
- **Cost**: Free tier available

### TTS (Text-to-Speech)
- **Provider**: Replicate
- **Model**: minimax/speech-02-hd
- **Voice**: Friendly_Person (configurable)
- **Emotion**: Happy (configurable)
- **Cost**: Pay-per-use via Replicate credits

### AI Response Generation
- **Primary**: Cerebras (qwen-3-235b-a22b-instruct-2507)
- **Fallback 1**: Groq (openai/gpt-oss-120b)
- **Fallback 2**: ChatAnywhere (gpt-4o-mini)
- **Context Window**: Recent 20 voice transcripts + 30 text messages

## Best Practices

### When to Enable
✅ Study groups with regular voice discussions
✅ Project collaboration calls
✅ Q&A sessions where bot can provide information
✅ Groups with 3+ active participants

### When to Disable or Use Quiet Hours
❌ Late night hours (use `/callquiet`)
❌ Personal/private conversations
❌ Calls with only 1-2 people (adjust `/callconfig`)
❌ When call quality is poor (high error rates)

### Optimal Settings
- **Min Participants**: 2-3 for small groups, 4-5 for large groups
- **Quiet Hours**: 22:00 to 08:00 (adjust to your timezone)
- **Audio Mode**: Enable only if TTS is working well
- **AI Features**: Keep `/boton` for full functionality

## Troubleshooting

### Bot Not Responding to Voice Messages

1. **Check if feature is enabled**: `/callstatus`
2. **Verify AI is on**: `/aistatus`
3. **Check quiet hours**: `/callstatus` shows current configuration
4. **Check participant count**: Might be below minimum threshold
5. **Check logs**: Look for transcription errors

### Transcription Errors

If you see "⚠️ I'm having trouble hearing the call":
- Voice messages might be too quiet or noisy
- Audio quality is poor (network issues)
- Language mismatch (bot expects English by default)
- API rate limits or quota exceeded

**Solution**: 
- Use `/calloff` and `/callon` to reset
- Check Groq API key and quotas
- Ensure voice messages are clear

### Too Many/Too Few Responses

**Too Many Responses**:
- Response probability is 30% - this is hardcoded for balance
- Rate limiting ensures 30s minimum between responses
- Consider disabling if still too chatty

**Too Few Responses**:
- Check if cooldown has expired (30s)
- Verify AI providers are working (`/aistatus`)
- Check for transcription errors in logs

## API Requirements

### Required API Keys
- `GROQ_API_KEY` - For STT (Whisper) and LLM fallback
- `CEREBRAS_API_KEY` or `CHATANYWHERE_API_KEY` - For LLM responses
- `REPLICATE_API_KEY` - For TTS (optional, only if audio mode is used)

### Recommended Setup
```bash
export GROQ_API_KEY="your_groq_key"
export CEREBRAS_API_KEY="your_cerebras_key"
export REPLICATE_API_KEY="your_replicate_key"  # Optional
```

## Privacy & Safety Considerations

### Data Handling
- Voice transcripts are stored temporarily (last 20 messages)
- Transcripts are cleared when calls end or feature is disabled
- No persistent storage of audio files (temporary files are deleted immediately)
- Chat history follows existing retention (last 30 messages)

### Telegram Bot API Limitations
- Telegram's Bot API does NOT support joining actual voice/video calls
- This feature works by processing voice MESSAGES sent during calls
- Users must send voice messages for the bot to participate
- The bot cannot hear live audio streams in group calls

### User Consent
- Admins control when proactive features are active
- Users in the group should be aware the bot transcribes voice messages
- Clear indicators when bot is active (check `/callstatus`)

## Future Enhancements

Potential improvements for future versions:
- [ ] Automatic language detection for transcription
- [ ] Custom voice selection for TTS
- [ ] Sentiment analysis for emotion-aware responses
- [ ] Call summary generation at end of calls
- [ ] Integration with Telegram's actual group call API (when available)
- [ ] Multiple language support in responses
- [ ] Call recording and transcript export

## Support & Feedback

If you encounter issues:
1. Check this documentation first
2. Review logs for error messages
3. Verify all API keys are configured correctly
4. Test with simple voice messages first
5. Report persistent issues with logs and configuration details

---

**Last Updated**: 2024
**Feature Version**: 1.0
**Compatible Bot Version**: v2.0+
