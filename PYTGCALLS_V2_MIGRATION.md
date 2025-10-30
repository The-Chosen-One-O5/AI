# pytgcalls v2.2.8 API Migration

## Overview
This document describes the migration from pytgcalls v1.x API to v2.2.8 API completed on this codebase.

## Changes Made

### 1. Import Changes

**Old (v1.x):**
```python
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
```

**New (v2.2.8):**
```python
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality
```

### 2. Joining Voice Calls

**Old API:**
```python
await pytg_client.join_group_call(
    chat_id,
    AudioPiped(audio_path),
    stream_type=StreamType().pulse_stream
)
```

**New API:**
```python
await pytg_client.play(
    chat_id,
    MediaStream(
        audio_path=audio_path,
        audio_parameters=AudioQuality.HIGH
    )
)
```

### 3. Leaving Voice Calls

**Old API:**
```python
await pytg_client.leave_group_call(chat_id)
```

**New API:**
```python
await pytg_client.leave_call(chat_id)
```

### 4. Changing/Streaming Audio

**Old API:**
```python
await pytg_client.change_stream(
    chat_id,
    AudioPiped(new_audio_path)
)
```

**New API:**
```python
await pytg_client.play(
    chat_id,
    MediaStream(
        audio_path=new_audio_path,
        audio_parameters=AudioQuality.HIGH
    )
)
```

## Files Modified

1. **main.py** (primary bot file)
   - Line 38-40: Updated imports
   - Lines 774-781: Updated `join_voice_chat()` function
   - Line 832: Updated `leave_voice_chat()` function
   - Lines 918-925: Updated `stream_tts_to_call()` function
   - Lines 972-979: Updated `play_audio_to_call()` function

2. **main_telethon.py** (migration script)
   - Lines 46-48: Updated imports

## AudioQuality Values

The new API uses an enum for audio quality:

- `AudioQuality.STUDIO` = (96000 Hz, 2 channels)
- `AudioQuality.HIGH` = (48000 Hz, 2 channels) ← **Used in this codebase**
- `AudioQuality.MEDIUM` = (36000 Hz, 1 channel)
- `AudioQuality.LOW` = (24000 Hz, 1 channel)

## Installation

pytgcalls v2.2.8 is installed from GitHub in the Dockerfile:

```dockerfile
RUN pip install --no-cache-dir git+https://github.com/pytgcalls/pytgcalls.git
```

This installs the latest version from the main branch, which is currently v2.2.8.

## Testing

Run the test suite to verify the migration:

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/engine/.local/lib/python3.12/site-packages')

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

print("✅ pytgcalls v2.2.8 API imports successful")
EOF
```

## Breaking Changes Summary

1. **Removed:** `StreamType` class - no longer needed
2. **Removed:** `AudioPiped`, `AudioVideoPiped` - replaced by `MediaStream`
3. **Removed:** `HighQualityAudio` - replaced by `AudioQuality` enum
4. **Removed:** Module `pytgcalls.types.input_stream` - doesn't exist in v2
5. **Renamed:** `join_group_call()` → `play()`
6. **Renamed:** `leave_group_call()` → `leave_call()`
7. **Removed:** `change_stream()` - use `play()` again to change stream

## Compatibility

- ✅ pytgcalls v2.2.8 (current)
- ❌ pytgcalls v1.x (no longer supported)

## References

- pytgcalls GitHub: https://github.com/pytgcalls/pytgcalls
- pytgcalls Documentation: Check repo README for latest API docs
