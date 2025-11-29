import os
import logging
import edge_tts
import asyncio
import tempfile
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from bytez import Bytez

logger = logging.getLogger(__name__)

# --- Audio Configuration ---
# Simple in-memory storage for user voice preferences
user_voices = {}

AVAILABLE_VOICES = {
    "guy": "en-US-GuyNeural",
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural",
    "brian": "en-GB-RyanNeural",
    "sonia": "en-GB-SoniaNeural"
}

# TTS API Configuration
TTS_API_URL = os.environ.get("TTS_API_URL")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

TTS_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer", "verse"]
user_tts_voices = {}  # Store TTS voice preference per user

# --- Bytez Configuration ---
def get_bytez_client():
    key = os.environ.get("BYTEZ_KEY")
    if not key:
        return None
    return Bytez(key)

# --- Core Logic Functions ---

async def generate_audio_file(text: str, voice: str) -> str:
    """Generates audio and returns the path to the temporary file."""
    try:
        # Create a temp file that persists after closing so we can read it
        # delete=False is important for Windows if we want to re-open it, 
        # but here we just need the path. 
        # Better: use a named temp file and let the caller handle cleanup or return bytes.
        # For simplicity and compatibility with existing structure, we'll return a path.
        
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd) # Close the file descriptor immediately
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(path)
        return path
    except Exception as e:
        logger.error(f"Audio generation error: {e}")
        raise e

async def generate_tts_api_audio(text: str, voice: str = "ash", emotion: str = "energetic") -> bytes | None:
    """Generates audio using the TTS API and returns the audio bytes."""
    if not TTS_API_URL or not TTS_API_KEY:
        logger.warning("TTS_API_URL or TTS_API_KEY not configured")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {TTS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice,
            "prompt": f"{emotion}, expressive, warm",
            "voice_metadata": {
                "emotion": emotion,
                "intensity": 5,
                "pacing": "normal",
                "vocal_traits": "expressive, warm"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(TTS_API_URL, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"TTS API error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"TTS API generation error: {e}")
        return None

async def generate_image_url(prompt: str) -> str | None:
    """Generates an image and returns the URL."""
    client = get_bytez_client()
    if not client:
        raise ValueError("BYTEZ_KEY not found.")

    def run_model():
        model = client.model("stabilityai/stable-diffusion-xl-base-1.0")
        return model.run(prompt)

    result = await asyncio.to_thread(run_model)
    if result.output:
        return result.output
    
    if hasattr(result, 'error'):
        raise Exception(result.error)
    return None

async def generate_video_url(prompt: str) -> str | None:
    """Generates a video and returns the URL."""
    client = get_bytez_client()
    if not client:
        raise ValueError("BYTEZ_KEY not found.")

    def run_model():
        # Using the model from the original snippet
        model = client.model("ali-vilab/text-to-video-ms-1.7b") 
        return model.run(prompt)

    result = await asyncio.to_thread(run_model)
    if result.output:
        return result.output
    return None

async def analyze_image_url(image_url: str) -> str | None:
    """Analyzes an image URL and returns the caption."""
    client = get_bytez_client()
    if not client:
        raise ValueError("BYTEZ_KEY not found.")

    def run_model():
        model = client.model("Salesforce/blip-image-captioning-base")
        return model.run({"url": image_url})

    result = await asyncio.to_thread(run_model)
    if result.output:
        return result.output
    return None


# --- Handlers ---

async def handle_audioselect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selects a voice for TTS."""
    args = context.args
    if not args:
        voice_list = "\n".join([f"- `{k}`" for k in AVAILABLE_VOICES.keys()])
        await update.message.reply_text(f"Available voices:\n{voice_list}\n\nUsage: /audioselect <voice_name>")
        return

    voice_name = args[0].lower()
    if voice_name in AVAILABLE_VOICES:
        user_voices[update.effective_user.id] = AVAILABLE_VOICES[voice_name]
        await update.message.reply_text(f"Voice set to: **{voice_name.capitalize()}**")
    else:
        await update.message.reply_text("Invalid voice name. Use /audioselect to see options.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates audio from text."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /audio <text>")
        return

    user_id = update.effective_user.id
    voice = user_voices.get(user_id, "en-US-GuyNeural") # Default voice

    status_msg = await update.message.reply_text("🎙️ Generating audio...")
    
    output_file = None
    try:
        output_file = await generate_audio_file(text, voice)
        await update.message.reply_audio(audio=open(output_file, 'rb'), title="AI Audio", caption=f"Voice: {voice}")
    except Exception as e:
        logger.error(f"Audio handler error: {e}")
        await status_msg.edit_text("❌ Failed to generate audio.")
    finally:
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {output_file}: {e}")
        
        try:
            await status_msg.delete()
        except:
            pass

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an image using Stable Diffusion XL."""
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usage: /image <prompt>")
        return

    status_msg = await update.message.reply_text("🎨 Painting your imagination...")

    try:
        image_url = await generate_image_url(prompt)
        if image_url:
            await update.message.reply_photo(photo=image_url, caption=f"🎨 {prompt}")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Image generation failed.")
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_askit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captions an image replied to by the user."""
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Please reply to an image with /askit.")
        return

    status_msg = await update.message.reply_text("👀 Analyzing image...")

    try:
        # Get the highest resolution photo
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_url = file.file_path

        caption = await analyze_image_url(image_url)

        if caption:
            await update.message.reply_text(f"👀 I see: {caption}")
            await status_msg.delete()
        else:
             await status_msg.edit_text("❌ Could not analyze image.")

    except Exception as e:
        logger.error(f"Vision error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a video using LTX-Video."""
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usage: /video <prompt>")
        return

    status_msg = await update.message.reply_text("🎬 Directing scene (this may take a while)...")

    try:
        video_url = await generate_video_url(prompt)
        if video_url:
            await update.message.reply_video(video=video_url, caption=f"🎬 {prompt}")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Video generation failed.")

    except Exception as e:
        logger.error(f"Video generation error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_tts_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selects a TTS voice for speak mode."""
    args = context.args
    if not args:
        voice_list = "\n".join([f"- `{v}`" for v in TTS_VOICES])
        await update.message.reply_text(f"🎤 Available TTS voices:\n{voice_list}\n\nUsage: /ttsvoice <voice_name>")
        return

    voice_name = args[0].lower()
    if voice_name in TTS_VOICES:
        user_tts_voices[update.effective_user.id] = voice_name
        await update.message.reply_text(f"🎤 TTS voice set to: **{voice_name.capitalize()}**")
    else:
        await update.message.reply_text(f"❌ Invalid voice name. Use /ttsvoice to see available options.")

async def send_audio_response(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper function to send a response as audio."""
    user_id = update.effective_user.id
    voice = user_tts_voices.get(user_id, "ash")
    
    status_msg = await update.message.reply_text("🎤 Generating audio response...")
    
    try:
        audio_bytes = await generate_tts_api_audio(text, voice=voice)
        if audio_bytes:
            await update.message.reply_audio(audio=audio_bytes, title="AI Response")
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text("❌ Failed to generate audio. Using text instead.")
            await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Audio send error: {e}")
        await status_msg.edit_text("❌ Error generating audio.")
        await update.message.reply_text(text)
