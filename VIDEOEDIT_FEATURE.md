# Image-to-Video Generation Feature

## Overview
Added a new `/videoedit` command that generates videos from images using the `free/wan-2.1-i2v-14b-720p` model via Replicate API.

## Implementation Details

### New Handler: `videoedit_handler`
- **Location**: `main.py` (lines 1608-1752)
- **Registration**: Added to handlers list in the "Image Commands" section (line 2003)
- **Help Text**: Updated to include the new command (line 1302)

### Command Usage
```
/videoedit [prompt]
```

**Requirements:**
- Command must be used as a reply to an image message
- Prompt is required and describes the desired video animation/transformation
- AI must be enabled for the chat group
- Replicate API key must be configured

### Features Implemented

1. **Input Validation**
   - Checks if AI is enabled for the chat
   - Verifies the command is replying to an image
   - Ensures a prompt is provided
   - Validates Replicate API key is configured

2. **Image Processing**
   - Downloads the replied image from Telegram
   - Converts to BytesIO format for Replicate API
   - Passes image and prompt to the model

3. **Video Generation**
   - Uses Replicate's `free/wan-2.1-i2v-14b-720p` model
   - Runs in separate thread to avoid blocking the bot
   - Handles multiple output formats (string URL, list of URLs)
   - Downloads generated video from Replicate's CDN

4. **User Feedback**
   - Shows "Generating video..." message during processing
   - Updates to "Downloading video..." when ready
   - Sends the generated video as a reply to the original image
   - Deletes status messages after successful completion

5. **Error Handling**
   - AI disabled for chat
   - Missing image in reply
   - Missing prompt
   - Missing API key
   - Replicate API failures
   - HTTP errors during download
   - Timeout handling (300 second timeout)
   - Invalid response formats

### Model Information
- **Model**: `free/wan-2.1-i2v-14b-720p`
- **Type**: Image-to-Video (I2V)
- **Provider**: Replicate (via free tier)
- **Input**: Image file + text prompt
- **Output**: Video URL (MP4 format)

### Technical Considerations

1. **Async Operation**: Uses `asyncio.to_thread()` to run the blocking Replicate API call without blocking the event loop

2. **Timeout**: 300-second timeout for both video generation and download to handle long-running operations

3. **File Handling**: Uses BytesIO for in-memory image handling, avoiding disk I/O

4. **Error Recovery**: Graceful degradation with informative error messages for users

5. **Resource Management**: Properly closes connections and cleans up status messages

## Testing Checklist

- [x] Syntax validation (Python compilation)
- [x] Handler registration
- [x] Help text updated
- [ ] Test with valid image and prompt
- [ ] Test without replying to image
- [ ] Test without prompt
- [ ] Test with AI disabled
- [ ] Test timeout handling
- [ ] Test with various image formats

## Dependencies
- `replicate`: Replicate API client
- `httpx`: Async HTTP client for downloading videos
- `asyncio`: For async/thread management
- `io`: BytesIO for in-memory file handling
- Existing Telegram bot libraries

## Configuration Required
- `REPLICATE_API_KEY` environment variable must be set
- AI must be enabled for the chat using `/boton`
