import logging
import random
from datetime import datetime, time
import pytz
import httpx
import io
import json
import base64
import os
from collections import deque
import shlex
import asyncio
import re
from threading import Thread # Needed for keep_alive

# --- Library Imports ---
import replicate
import emoji
import edge_tts
from openai import AsyncOpenAI, OpenAIError
from cerebras.cloud.sdk import Cerebras
from groq import AsyncGroq
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D
from PIL import Image
from bs4 import BeautifulSoup
from telegraph import Telegraph
from telegram import Update, ChatPermissions, InputFile, ReactionTypeEmoji
from telegram.ext import Application, CommandHandler, MessageHandler, PollAnswerHandler, ContextTypes, filters
from telegram.error import BadRequest
from flask import Flask # Needed for keep_alive

# --- Keep Alive Server Setup ---
keep_alive_app = Flask('')

@keep_alive_app.route('/')
def keep_alive_home():
    return "I'm alive!"

def run_keep_alive():
    port = int(os.environ.get('PORT', 8080))
    keep_alive_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_keep_alive)
    t.start()
    print("Keep-alive server started.")

# --- Configuration (using Environment Variables) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TARGET_CHAT_ID = int(os.environ.get('TARGET_CHAT_ID', '-1001937965792')) # Default if not set
CONFIG_FILE = "config.json" # For non-sensitive settings
MEMORY_FILE = "memory.json"
GOSSIP_FILE = "gossip.json"
TYPEGPT_FAST_API_KEY = os.environ.get('TYPEGPT_FAST_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
CHATANYWHERE_API_KEY = os.environ.get('CHATANYWHERE_API_KEY')
FALLBACK_API_KEY = os.environ.get('FALLBACK_API_KEY')
BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY')
GROK_API_KEY = os.environ.get('GROK_API_KEY')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
REPLICATE_API_KEY = os.environ.get('REPLICATE_API_KEY')
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
SAMURAI_API_KEY = os.environ.get('SAMURAI_API_KEY') # New key for Text-to-Video

# --- AI MODEL CONFIGURATION ---
# Models used by the bot (for easy reference and updates):
# 
# Primary LLM Chain (Cerebras → Groq → ChatAnywhere):
#   1. Cerebras: llama3.1-70b
#   2. Groq: openai/gpt-oss-120b
#   3. ChatAnywhere: gpt-4o-mini
#
# Vision Models:
#   - TypeGPT Fast: gemini-2.5-pro
#   - OpenRouter: moonshotai/kimi-vl-a3b-thinking:free
#
# Audio/TTS:
#   - Edge TTS (Free, unlimited): Default voice "en-US-GuyNeural"
#
# Image Generation:
#   - Infip API: Qwen model
#
# Note: Update these models in their respective functions if providers deprecate them.
# Check deprecation notices: https://console.groq.com/docs/deprecations

# Exit if essential token is missing
if not BOT_TOKEN:
    print("FATAL ERROR: BOT_TOKEN environment variable not set!")
    exit()
if REPLICATE_API_KEY:
    os.environ['REPLICATE_API_TOKEN'] = REPLICATE_API_KEY # Replicate specifically needs this env var


# --- State Management ---
chat_histories = {}
active_random_jobs = set()
trivia_sessions = {}

# --- Edge TTS Voice Configuration ---
DEFAULT_TTS_VOICE = "en-US-GuyNeural"  # Deep male voice
AVAILABLE_TTS_VOICES = {
    "guy": "en-US-GuyNeural",  # Deep male (default)
    "davis": "en-US-DavisNeural",  # Deep male
    "tony": "en-US-TonyNeural",  # Male
    "jason": "en-US-JasonNeural",  # Male
    "jenny": "en-US-JennyNeural",  # Female
    "aria": "en-US-AriaNeural",  # Female
    "sara": "en-US-SaraNeural",  # Female
    "brian": "en-GB-RyanNeural",  # British male
    "sonia": "en-GB-SoniaNeural",  # British female
}

# --- Daily Reminder Configuration ---
JEE_MAINS_DATE = datetime(2026, 1, 22).date()
JEE_ADV_DATE = datetime(2026, 5, 18).date()
MOTIVATIONAL_QUOTES = [
    "Either you run the day or the day runs you.",
    "The secret of getting ahead is getting started.",
    "Believe you can and you're halfway there.",
]

# --- Standard Bot Setup ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config & Memory Persistence ---
def load_config() -> dict:
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Default non-sensitive settings
        return {
            "reminder_time": "04:00", "moderation_enabled": True,
            "random_chat_config": {}, "ai_enabled_config": {},
            "audio_mode_config": {}, "tts_voice_config": {}
        }

def save_config(config: dict) -> None:
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

def load_memory() -> dict:
    try:
        with open(MEMORY_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_memory(memory: dict) -> None:
    try:
        with open(MEMORY_FILE, 'w') as f: json.dump(memory, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")


def load_gossip() -> dict:
    try:
        with open(GOSSIP_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_gossip(gossip: dict) -> None:
    try:
        with open(GOSSIP_FILE, 'w') as f: json.dump(gossip, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save gossip: {e}")


# --- Helper Functions ---

async def delete_message_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.data['chat_id'], message_id=job.data['message_id'])
    except BadRequest: pass # Ignore if message already deleted

async def send_deletable_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_to_message_id: int | None = None):
    try:
        sent_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id, parse_mode='Markdown')
        if context.job_queue:
            context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.message_id})
        return sent_message
    except BadRequest as e:
        logger.error(f"Failed to send deletable message (Markdown maybe?): {e}")
        # Fallback to plain text if Markdown fails
        try:
            sent_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)
            if context.job_queue:
                context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.message_id})
            return sent_message
        except Exception as e2:
            logger.error(f"Failed to send deletable message even as plain text: {e2}")
            return None # Indicate failure


async def generate_audio_from_text(text: str, voice: str = DEFAULT_TTS_VOICE) -> bytes | None:
    """Generate audio from text using Edge TTS (free and unlimited)."""
    cleaned_text = re.sub(r'[*_`]', '', text)  # Remove markdown for cleaner TTS
    if not cleaned_text.strip():
        logger.warning("No text to convert to audio after cleaning")
        return None
    
    # Use /tmp for temp files (more reliable across platforms)
    temp_file = f"/tmp/tts_temp_{id(text)}_{random.randint(1000, 9999)}.mp3"
    
    try:
        logger.info(f"Generating audio with Edge TTS using voice: {voice}")
        logger.info(f"Text length: {len(cleaned_text)} characters")
        logger.info(f"Temp file: {temp_file}")
        
        # Generate TTS using Edge TTS Communicate API
        communicate = edge_tts.Communicate(cleaned_text, voice)
        await communicate.save(temp_file)
        
        # Verify file was created and has content
        if not os.path.exists(temp_file):
            logger.error(f"Temp file was not created: {temp_file}")
            return None
        
        file_size = os.path.getsize(temp_file)
        logger.info(f"Audio file created: {file_size} bytes")
        
        if file_size == 0:
            logger.error("Generated audio file is empty")
            os.remove(temp_file)
            return None
        
        # Read the generated file
        with open(temp_file, 'rb') as f:
            audio_bytes = f.read()
        
        logger.info(f"Successfully generated audio: {len(audio_bytes)} bytes")
        
        # Clean up temp file
        try:
            os.remove(temp_file)
            logger.debug(f"Cleaned up temp file: {temp_file}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temp file {temp_file}: {cleanup_error}")
        
        return audio_bytes
        
    except FileNotFoundError as e:
        logger.error(f"File not found error during audio generation: {e}")
        return None
    except PermissionError as e:
        logger.error(f"Permission error during audio generation: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate audio with Edge TTS: {e}", exc_info=True)
        # Clean up temp file if it exists
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temp file after error: {cleanup_error}")
        return None

async def generate_video_from_text(prompt: str) -> bytes | None:
    """Generates video from text using the Samurai API."""
    if not SAMURAI_API_KEY:
        logger.error("Samurai API key not configured. Cannot generate video.")
        return None

    logger.info(f"Generating video with Samurai API for prompt: {prompt}")
    # Assuming an OpenAI-compatible endpoint and payload structure
    api_url = "https://samuraiapi.in/v1/videos/generations" # Assumed endpoint
    headers = {
        "Authorization": f"Bearer {SAMURAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "wan-ai-wan2.1-t2v-14b",
        "prompt": prompt,
        "n": 1, # Request one video
        # Add other parameters like size, fps, etc., if supported by the API
        # "size": "1024x576",
        # "fps": 24
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client: # Longer timeout for video
            response = await client.post(api_url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"Samurai Video API error: {response.status_code} - {response.text}")
                return None

            result_data = response.json().get("data")
            # Assuming the response structure is similar to OpenAI's image gen, returning a URL
            if result_data and isinstance(result_data, list) and result_data[0].get("url"):
                video_url = result_data[0]["url"]
                logger.info(f"Downloading generated video from: {video_url}")

                # Download the video file
                video_response = await client.get(video_url, timeout=300.0) # Long timeout for download
                video_response.raise_for_status() # Check for download errors
                logger.info("Video downloaded successfully.")
                return video_response.content
            else:
                logger.error(f"Samurai Video API response did not contain expected URL: {response.json()}")
                return None

    except httpx.TimeoutException:
        logger.error("Samurai Video API timed out.")
        return None
    except Exception as e:
        logger.error(f"Failed to generate video with Samurai API: {e}", exc_info=True)
        return None

def create_telegraph_page(title: str, content: str, config: dict) -> str | None:
    try:
        # Assuming Telegraph library is thread-safe or used carefully
        telegraph_token = config.get("telegraph_token")
        telegraph = Telegraph(access_token=telegraph_token)
        if not telegraph_token:
            try:
                new_account = telegraph.create_account(short_name='AI618Bot') # Or any short name
                config["telegraph_token"] = new_account.get('access_token')
                save_config(config) # Save the new token immediately
                logger.info("Created new Telegraph account.")
            except Exception as create_e:
                logger.error(f"Failed to create Telegraph account: {create_e}")
                return None # Cannot proceed without account/token

        # Convert simple markdown bold/italic and newlines to HTML
        html_content = content.replace('\n', '<br>')
        html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'_(.*?)_', r'<em>\1</em>', html_content)
        html_content = re.sub(r'`(.*?)`', r'<code>\1</code>', html_content)


        response = telegraph.create_page(title=title, html_content=html_content)
        return response.get('url')
    except Exception as e:
        logger.error(f"Failed to create Telegraph page: {e}")
        return None

async def send_final_response(update: Update, context: ContextTypes.DEFAULT_TYPE, response_text: str | None, thinking_message, prompt_title: str):
    if not response_text:
        try:
            error_message = (
                "Sorry, I couldn't get a response right now. All AI providers are unavailable.\n"
                "This might be due to:\n"
                "• API rate limits\n"
                "• Model deprecation or maintenance\n"
                "• Network issues\n\n"
                "Please try again in a few moments."
            )
            await context.bot.edit_message_text(error_message, chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        except BadRequest: pass # Ignore if original message deleted
        return

    config = load_config()
    chat_id = str(update.message.chat_id)
    is_audio_mode = config.get("audio_mode_config", {}).get(chat_id, False)

    if is_audio_mode:
        try:
            await context.bot.edit_message_text("🎤 Generating audio...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        except BadRequest: pass # Ignore if original message deleted

        # Get the configured voice for this chat
        voice = config.get("tts_voice_config", {}).get(chat_id, DEFAULT_TTS_VOICE)
        logger.info(f"Audio mode enabled for chat {chat_id}, using voice: {voice}")
        
        audio_bytes = await generate_audio_from_text(response_text, voice)
        if audio_bytes:
            logger.info(f"Audio generated successfully, sending to Telegram ({len(audio_bytes)} bytes)")
            try:
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio_bytes)
                logger.info("Audio sent successfully to Telegram")
                # Delete thinking message after sending audio
                try: await thinking_message.delete()
                except BadRequest: pass
            except Exception as e:
                 logger.error(f"Failed to send voice message to Telegram: {e}", exc_info=True)
                 # Fallback to text if sending voice fails
                 try:
                     await context.bot.edit_message_text("Failed to send audio, sending text.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                 except BadRequest: pass
                 await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)
        else:
            logger.error("Audio generation returned None, falling back to text")
            try:
                await context.bot.edit_message_text("Audio generation failed, sending text.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            except BadRequest: pass
            await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)
    else:
        # Send as text or telegraph page
        await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)

async def send_or_telegraph_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE, response_text: str, thinking_message, prompt_title: str):
    try:
        if len(response_text) > 4000:
            await context.bot.edit_message_text("Response too long, creating Telegraph page...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            # Run blocking telegraph creation in a separate thread
            url = await asyncio.to_thread(create_telegraph_page, prompt_title, response_text, load_config())
            final_message = f"The response was too long. I've posted it here:\n{url}" if url else f"Response too long, and failed to post to Telegraph. Truncated:\n\n{response_text[:3800]}..."
            await context.bot.edit_message_text(final_message, chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        else:
            # Try sending with Markdown, fall back to plain text if it fails
            try:
                await context.bot.edit_message_text(response_text, chat_id=update.effective_chat.id, message_id=thinking_message.message_id, parse_mode='Markdown')
            except BadRequest:
                logger.warning("Markdown parsing failed, sending as plain text.")
                await context.bot.edit_message_text(response_text, chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
    except BadRequest as e:
         # Handle cases where the thinking_message might have been deleted already
         if "Message to edit not found" in str(e):
             logger.warning("Thinking message was likely deleted before final response.")
             # Optionally send response as a new message if edit fails
             # await update.message.reply_text(response_text[:4000]) # Example
         else:
             logger.error(f"Failed to edit message: {e}")
    except Exception as e:
         logger.error(f"Unexpected error in send_or_telegraph_fallback: {e}")


async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if chat_id > 0: return False # No admins in private chats
    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in chat_admins)
    except BadRequest:
        logger.warning(f"Could not get admins for chat {chat_id}. Assuming user {user_id} is not admin.")
        return False

# --- AI API Call Chain ---
async def call_cerebras_api(messages: list) -> str | None:
    """PRIMARY API: Cerebras Model (Direct SDK)."""
    if not CEREBRAS_API_KEY:
        logger.warning("Cerebras API Key not set, skipping.")
        return None
    logger.info("Trying Primary API: Cerebras Direct")

    try:
        client = Cerebras(api_key=CEREBRAS_API_KEY)

        # Run the blocking SDK call in a separate thread
        def run_cerebras_sync():
            stream = client.chat.completions.create(
                messages=messages,
                model="qwen-3-235b-a22b-instruct-2507",
                stream=True,
                max_tokens=8000,
                temperature=0.7,
                top_p=0.8
            )
            full_response = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
            return full_response

        response_content = await asyncio.to_thread(run_cerebras_sync)

        if response_content:
            logger.info(f"Cerebras API returned response: {len(response_content)} chars")
            return response_content.strip()
        else:
            logger.warning("Cerebras API returned empty content.")
            return None

    except OpenAIError as e:
        logger.error(f"Cerebras API OpenAI-compatible error: {e}")
        return None
    except Exception as e:
        logger.warning(f"Cerebras API failed with exception: {e}", exc_info=True)
        return None

async def call_groq_lpu_api(messages: list) -> str | None:
    """FALLBACK 1: Groq LPU Model (Direct API)."""
    if not GROQ_API_KEY:
        logger.warning("Groq API Key not set, skipping.")
        return None
    logger.warning("--- Cerebras failed. Trying Groq LPU Direct ---")

    try:
        from groq import BadRequestError
        client = AsyncGroq(api_key=GROQ_API_KEY)

        chat_completion = await client.chat.completions.create(
            messages=messages,
            model="openai/gpt-oss-120b",
            temperature=0.7,
            max_tokens=4096,
            top_p=0.8,
            stream=False # Get the full response at once
        )

        response_content = chat_completion.choices[0].message.content
        if response_content:
            logger.info(f"Groq API returned response: {len(response_content)} chars")
            return response_content.strip()
        else:
            logger.warning("Groq API returned empty content.")
            return None

    except BadRequestError as e:
        logger.error(f"Groq API BadRequestError (possibly deprecated model): {e}")
        return None
    except Exception as e:
        logger.warning(f"Groq API failed with exception: {e}", exc_info=True)
        return None

async def call_chatanywhere_api(messages: list) -> str | None:
    """FALLBACK 2: ChatAnywhere API."""
    if not CHATANYWHERE_API_KEY:
        logger.warning("ChatAnywhere API Key not set, skipping.")
        return None
    
    api_url = "https://api.chatanywhere.tech/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CHATANYWHERE_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4o-mini", "messages": messages, "max_tokens": 4096}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                response_content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if response_content:
                    logger.info(f"ChatAnywhere API returned response: {len(response_content)} chars")
                    return response_content
            elif response.status_code == 400:
                logger.error(f"ChatAnywhere API BadRequest (possibly deprecated model): {response.text}")
            else:
                logger.warning(f"ChatAnywhere API failed with status {response.status_code}: {response.text}")
    except httpx.TimeoutException:
        logger.warning("ChatAnywhere API request timed out")
    except httpx.RequestError as e:
        logger.warning(f"ChatAnywhere API network error: {e}")
    except Exception as e:
        logger.warning(f"ChatAnywhere API failed with exception: {e}", exc_info=True)
    return None
async def get_typegpt_response(messages: list) -> str | None:
    # --- FULL FALLBACK CHAIN ---
    logger.info("--- Starting AI Fallback Chain ---")

    # 1. Primary: Cerebras Direct SDK
    if CEREBRAS_API_KEY:
        response = await call_cerebras_api(messages) # New primary
        if response: logger.info("--- Chain Success: Cerebras ---"); return response
    else: logger.warning("Cerebras API Key not set, skipping.")

    # 2. Fallback 1: Groq LPU Direct API
    if GROQ_API_KEY:
        # Logging message handled inside call_groq_lpu_api
        response = await call_groq_lpu_api(messages) # New fallback 1
        if response: logger.info("--- Chain Success: Groq LPU ---"); return response
    else: logger.warning("Groq API Key not set, skipping.")

    # 3. Fallback 2: ChatAnywhere (Kept as further fallback)
    if CHATANYWHERE_API_KEY:
        logger.warning("--- Groq LPU failed. Trying ChatAnywhere ---")
        response = await call_chatanywhere_api(messages) # Ensure this function exists & is defined
        if response: logger.info("--- Chain Success: ChatAnywhere ---"); return response
    else: logger.warning("ChatAnywhere API Key not set, skipping.")

    logger.error("--- All available APIs in the fallback chain failed. ---")
    return None

async def get_typegpt_gemini_vision_response(messages: list) -> str | None:
    if not TYPEGPT_FAST_API_KEY: return None
    api_url = "https://fast.typegpt.net/v1/chat/completions"
    headers = {"Authorization": f"Bearer {TYPEGPT_FAST_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "gemini-2.5-pro", "messages": messages, "max_tokens": 4096}
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.warning(f"Gemini Vision API failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"Gemini Vision API failed: {e}")
    return None

async def get_baidu_ernie_vision_response(messages: list) -> str | None:
    if not OPENROUTER_API_KEY: return None
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost", "X-Title": "AI618 Bot"}
    payload = {"model": "moonshotai/kimi-vl-a3b-thinking:free", "messages": messages, "max_tokens": 4096}
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                 response_text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                 # Clean up potential thinking tags
                 cleaned_text = re.split(r'</?thinking>', response_text)[-1].strip()
                 cleaned_text = re.split(r'◁/?think▷', cleaned_text)[-1].strip()
                 return cleaned_text
            logger.warning(f"Baidu Ernie Vision API failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"Baidu Ernie Vision API failed: {e}")
    return None

# --- Tool Functions ---
async def execute_web_search(query: str) -> str:
    if not BRAVE_API_KEY: return "Web search disabled: API key not set."
    try:
        search_url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"}
        params = {"q": query}
        async with httpx.AsyncClient() as client:
            search_response = await client.get(search_url, headers=headers, params=params, timeout=30.0)
        if search_response.status_code != 200: return f"Brave API Error: {search_response.status_code}"
        results = search_response.json().get("web", {}).get("results", [])
        if not results: return "No web results found."
        top_urls = [result.get('url') for result in results[:3] if result.get('url')]
        if not top_urls: return "No valid URLs found in search results."
        scraping_tasks = [scrape_url_content(url) for url in top_urls]
        scraped_contents = await asyncio.gather(*scraping_tasks)
        combined_context = ""
        for i, content in enumerate(scraped_contents):
            if content: combined_context += f"--- Source {i+1}: {top_urls[i]} ---\n{content}\n\n"
        return combined_context if combined_context else "Could not read top pages (might have bot protection)."
    except Exception as e:
        logger.error(f"Execute web search failed: {e}")
        return f"An error occurred during search: {e}"

async def scrape_url_content(url: str) -> str | None:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove common non-content elements
        for element in soup(["script", "style", "nav", "footer", "aside", "header", "form"]):
            element.decompose()
        # Get text, strip whitespace, and limit length
        text = ' '.join(line.strip() for line in soup.get_text(separator=' ', strip=True).splitlines() if line.strip())
        return text[:3000] # Limit context size further if needed
    except Exception as e:
        logger.error(f"Failed to scrape URL {url}: {e}")
        return None

async def get_image_bytes_from_prompt(prompt: str) -> bytes | None:
    # Example using a placeholder API URL and Key - Replace if you have one
    # api_url = "YOUR_IMAGE_API_URL"
    # api_key = os.environ.get("YOUR_IMAGE_API_KEY")
    # if not api_key: logger.error("Image API key not set."); return None
    # headers = {"Authorization": f"Bearer {api_key}", ... }
    # payload = {"prompt": prompt, ... }
    # Using a known free/test endpoint for now
    api_url = "https://api.infip.pro/v1/images/generations"
    headers = {"Authorization": "Bearer infip-60b6cdd9", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "model": "Qwen", "n": 1, "size": "512x512"} # Sticker size
    try:
        logger.info(f"Requesting image generation for: {prompt}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            if response.status_code != 200:
                 logger.error(f"Image generation API error: {response.status_code} - {response.text}")
                 return None
            result_data = response.json().get("data")
            if not result_data or not isinstance(result_data, list) or not result_data[0].get("url"):
                 logger.error("Image API response malformed or missing URL.")
                 return None
            image_url = result_data[0]["url"]

            # Download the image
            logger.info(f"Downloading generated image from: {image_url}")
            image_response = await client.get(image_url, timeout=60.0)
            image_response.raise_for_status()
            logger.info("Image downloaded successfully.")
            return image_response.content
    except Exception as e:
        logger.error(f"Failed to get image bytes for sticker: {e}")
    return None

def process_image_for_sticker(image_bytes: bytes) -> io.BytesIO | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Ensure image is within 512x512, preserving aspect ratio
            img.thumbnail((512, 512))
            sticker_buffer = io.BytesIO()
            # Convert to RGBA first if needed by WEBP encoder, handle potential errors
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img.save(sticker_buffer, 'WEBP', lossless=True) # Use lossless for stickers
            sticker_buffer.seek(0)
            logger.info("Image successfully processed into WEBP sticker format.")
            return sticker_buffer
    except Exception as e:
        logger.error(f"Could not process image for sticker: {e}")
        return None

async def get_emoji_reaction(message_text: str) -> str | None:
    prompt = (
        "You are an emoji reaction bot. Analyze the message and respond with ONLY the single best emoji. "
        "Stick to simple, common emojis that are widely supported, like 👍, 😂, ❤️, 🙏, 🎉, 🤔, 😢, 🔥. "
        "Avoid obscure or very new emojis. For neutral messages, use '👍'.\n\n"
        f"--- Message ---\n{message_text}\n\n--- Your Emoji Response ---"
    )
    response = await get_typegpt_response([{"role": "system", "content": prompt}])
    if response:
        # Extract the first valid emoji from the response
        emoji_list = [c for c in response if c in emoji.EMOJI_DATA]
        if emoji_list:
            first_emoji = emoji_list[0]
            logger.info(f"AI returned valid emoji: {first_emoji}")
            return first_emoji
    logger.warning(f"AI did not return a valid emoji from response: '{response}'")
    return None

# --- Trivia System ---
async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles user answers to the bot's trivia quiz polls."""
    answer = update.poll_answer
    # Find the chat session associated with this poll ID
    chat_id = None
    session = None
    for cid, s in trivia_sessions.items():
        # Ensure poll ID matches and the game is in the polling state
        if s.get("current_poll_id") == answer.poll_id and s.get("state") == "polling":
            chat_id = cid
            session = s
            break
            
    if not session or not chat_id:
        # This is expected for answers to old polls, don't log as error unless debugging
        # logger.debug(f"Poll answer for unknown or inactive poll ID: {answer.poll_id}")
        return

    user_id = answer.user.id
    
    # Check if the user is a registered player for this game
    if user_id not in session["players"]:
        # Log if needed, but don't clutter logs too much
        # logger.info(f"Ignoring poll answer from non-player {user_id} in chat {chat_id}")
        return

    # --- Robust Check for Correctness ---
    chosen_index = -1 # Default to invalid index
    if answer.option_ids: # option_ids is empty if the user retracts their vote
        chosen_index = answer.option_ids[0]

    correct_index = session.get("current_correct_index")

    # Log the values being compared for debugging
    logger.debug(f"Chat {chat_id}, User {user_id}: Chose index {chosen_index} (type: {type(chosen_index)}), Correct index is {correct_index} (type: {type(correct_index)})")

    # Ensure both are integers before comparing
    is_correct = False
    if isinstance(chosen_index, int) and isinstance(correct_index, int) and chosen_index == correct_index:
        is_correct = True
        
    if is_correct:
        # Award 1 point for correct answer *only if not already awarded for this question*
        # (Telegram might send multiple updates, ensure score is added only once per question per user)
        # We'll rely on the poll closing logic to finalize scores, but track answers here
        # For simplicity now, let's just increment. If double-counting happens, we'll need a flag.
        session["players"][user_id]["score"] = session["players"][user_id].get("score", 0) + 1 # Use .get for safety
        logger.info(f"Player {user_id} in chat {chat_id} answered correctly. New tentative score: {session['players'][user_id]['score']}")
    else:
         # Log retraction or incorrect answer
         if not answer.option_ids:
              logger.info(f"Player {user_id} in chat {chat_id} retracted their vote.")
              # Optional: Decrement score if they previously answered correctly? Depends on rules.
         else:
              logger.info(f"Player {user_id} in chat {chat_id} answered incorrectly (chose {chosen_index}, needed {correct_index}).")

async def process_poll_end_callback(context: ContextTypes.DEFAULT_TYPE):
    """Job callback executed when a trivia poll's time expires."""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    expected_poll_id = job_data['expected_poll_id']

    session = trivia_sessions.get(chat_id)

    # Check if the game is still active and the poll ID matches the current one
    if not session or session["state"] != "polling" or session.get("current_poll_id") != expected_poll_id:
        logger.info(f"Ignoring stale poll end job for poll {expected_poll_id} in chat {chat_id}")
        return

    logger.info(f"Processing end of poll {expected_poll_id} in chat {chat_id}")

    # Announce the correct answer was handled implicitly by the poll closing
    # We can add a small summary message if desired, but let's keep it simple for now.
    
    # Check if the game should end
    if session["current_question_num"] >= session["total_questions"]:
        await end_trivia(context, chat_id, "That's the last question!")
    else:
        # Ask the next question after a short delay
        await asyncio.sleep(2) # Shorter delay after poll closes
        await ask_next_trivia_question(context, chat_id)
        
async def get_new_trivia_question(context: ContextTypes.DEFAULT_TYPE, topic: str, asked_questions: list) -> dict | None:
    """Gets a new, unique multiple-choice trivia question, options, and correct index from the AI."""
    
    history_prompt_part = ""
    if asked_questions:
        history = "\n - ".join(asked_questions)
        history_prompt_part = f"You have already asked these questions, DO NOT repeat them:\n - {history}\n\n"

    prompt = (
        f"You are a trivia game host generating multiple-choice questions about **{topic}**. {history_prompt_part}"
        "Generate ONE new question with exactly 4 plausible options (one correct, three incorrect). "
        "Format your response ONLY as a JSON object with three keys: "
        "'question' (string), 'options' (a list of 4 strings), and 'correct_index' (an integer from 0 to 3 indicating the correct option's index). "
        "Ensure options are concise. Do not add any other text or markdown."
    )
    messages = [{"role": "system", "content": prompt}]
    response_text = await get_typegpt_response(messages) # Use your reliable AI call chain
    if not response_text:
         logger.error("AI failed to generate trivia poll question text.")
         return None
    try:
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group(0))
            # Validate the structure
            if ('question' in data and isinstance(data['question'], str) and
                'options' in data and isinstance(data['options'], list) and len(data['options']) == 4 and
                'correct_index' in data and isinstance(data['correct_index'], int) and 0 <= data['correct_index'] <= 3):
                # Ensure options are strings
                data['options'] = [str(opt) for opt in data['options']]
                return data # Return the full dict: {'question': '...', 'options': [...], 'correct_index': ...}
            else:
                 logger.error(f"AI JSON has incorrect structure or types: {data}")
        else:
             logger.error(f"No JSON found in AI trivia poll response: {response_text}")
    except Exception as e:
        logger.error(f"Failed to parse trivia poll question: {e}\nResponse: {response_text}")
    return None

async def start_trivia(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str, question_count: int):
    chat_id = str(update.message.chat_id)
    if trivia_sessions.get(chat_id, {}).get("state") in ["registering", "asking"]:
        await update.message.reply_text("A game is already in progress!")
        return

    intro_text = (f"Alright, trivia time! 🔥 **{question_count}** rounds on **{topic}**.\n\n"
                  "Who's playing? Reply to this message with `me` to join.\n"
                  "When ready, someone reply `all in` to start!")
    intro_message = await update.message.reply_text(intro_text, parse_mode='Markdown')
    if not intro_message: # Handle case where sending message fails
         logger.error(f"Failed to send trivia intro message in chat {chat_id}")
         return

    trivia_sessions[chat_id] = {
        "state": "registering", # States: registering, polling, finished
        "topic": topic,
        "total_questions": question_count,
        "current_question_num": 0,
        "players": {}, # {user_id: {"username": str, "first_name": str, "score": int}}
        "registration_message_id": intro_message.message_id,
        "asked_questions": [],
        "current_poll_id": None, # Store poll ID instead of message ID
        "current_correct_index": None # Store correct index
    }

async def ask_next_trivia_question(context: ContextTypes.DEFAULT_TYPE, chat_id: str):
    """Fetches and sends the next trivia question as a Quiz Poll."""
    session = trivia_sessions.get(chat_id)
    if not session or session["state"] == "finished": return # Stop if game ended

    session["current_question_num"] += 1
    
    question_data = await get_new_trivia_question(context, session["topic"], session["asked_questions"])
    if not question_data:
        await end_trivia(context, chat_id, "I couldn't get a new question! Game ending.")
        return
        
    question_text = question_data['question']
    options = question_data['options']
    correct_index = question_data['correct_index']
    
    session["asked_questions"].append(question_text) # Remember question text
    session["current_correct_index"] = correct_index # Store correct index for scoring

    try:
        # Send the quiz poll - 60 second time limit
        poll_message = await context.bot.send_poll(
            chat_id=int(chat_id),
            question=f"Q{session['current_question_num']}/{session['total_questions']}: {question_text}",
            options=options,
            type='quiz',
            correct_option_id=correct_index,
            is_anonymous=False, # Important for scoring
            open_period=60 # Poll duration in seconds
        )
        session["current_poll_id"] = poll_message.poll.id
        session["state"] = "polling" # Update state

        # Schedule job to process results after poll closes + small buffer
        if context.job_queue:
            context.job_queue.run_once(
                 process_poll_end_callback,
                 62, # open_period + buffer
                 data={'chat_id': chat_id, 'expected_poll_id': poll_message.poll.id},
                 name=f"trivia_poll_end_{chat_id}_{poll_message.poll.id}"
             )
        else:
            logger.warning("Job queue is None in ask_next_trivia_question, cannot schedule poll end callback")

    except Exception as e:
        logger.error(f"Failed to send trivia poll: {e}")
        await end_trivia(context, chat_id, "Error sending poll, game ending.")

async def end_trivia(context: ContextTypes.DEFAULT_TYPE, chat_id: str, reason: str):
    session = trivia_sessions.get(chat_id, {})
    leaderboard = f"{reason}\n\n**Final Leaderboard:**\n"
    if session.get("players"):
        # Sort players by score (descending)
        sorted_players = sorted(session["players"].items(), key=lambda item: item[1]["score"], reverse=True)
        for i, (user_id, player_data) in enumerate(sorted_players):
            medal = "🥇🥈🥉"[i] if i < 3 else "🔹"
            mention = f"@{player_data['username']}" if player_data['username'] else player_data.get('first_name', f'User {user_id}') # Safely get first name
            leaderboard += f"{medal} {mention}: {player_data['score']} points\n"
    else:
        leaderboard += "No scores recorded."

    try:
        await context.bot.send_message(int(chat_id), leaderboard, parse_mode='Markdown')
    except Exception as e:
         logger.error(f"Failed to send final leaderboard: {e}")
    if chat_id in trivia_sessions:
        trivia_sessions[chat_id]["state"] = "finished" # Use 'finished' state # Mark game as over

# --- Master Handlers ---

async def smart_ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ensure update and message exist
    if not update.message or not update.message.text:
        return

    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt after /ai.")
        return

    chat_id_str = str(update.message.chat_id)
    config = load_config()
    # Check if AI features are enabled for this chat
    if not config.get("ai_enabled_config", {}).get(chat_id_str, False):
        await update.message.reply_text("AI features are currently disabled in this group. Ask an admin to use `/boton`.")
        return

    thinking_message = await update.message.reply_text("Processing...")

    try:
        # Trivia control commands (Admin only)
        trivia_match = re.search(r'start trivia(?: on (.+?))?(?: (\d+)Q)?$', prompt, re.IGNORECASE)
        if trivia_match:
            if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context):
                 await context.bot.edit_message_text("Only admins can start trivia games.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                 return
            topic = (trivia_match.group(1) or "general knowledge").strip()
            q_count = int(trivia_match.group(2) or 5)
            await thinking_message.delete() # Delete "Processing..." before starting game
            await start_trivia(update, context, topic, q_count)
            return
            
        if "stop trivia" in prompt.lower():
            if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context):
                 await context.bot.edit_message_text("Only admins can stop trivia games.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                 return
            if chat_id_str in trivia_sessions and trivia_sessions[chat_id_str].get("state") != "inactive":
                await thinking_message.delete()
                await end_trivia(context, chat_id_str, "The game was stopped early by an admin.")
            else:
                await context.bot.edit_message_text("No trivia game is currently running.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            return

        # Gossip Memory commands
        if update.message.reply_to_message and ("remember this" in prompt.lower()):
            replied = update.message.reply_to_message
            if replied.text:
                gossip = load_gossip()
                gossip.setdefault(chat_id_str, []).append({
                    "author": replied.from_user.first_name,
                    "author_username": replied.from_user.username,
                    "text": replied.text,
                    "saved_by": update.message.from_user.first_name,
                    "timestamp": datetime.now().isoformat()
                })
                save_gossip(gossip)
                await context.bot.edit_message_text("Alright, I'll remember that one.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            else:
                await context.bot.edit_message_text("I can only remember text messages.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            return

        if "gossip" in prompt.lower():
            gossip_list = load_gossip().get(chat_id_str, [])
            if gossip_list:
                random_gossip = random.choice(gossip_list)
                await context.bot.edit_message_text(f"Remember when {random_gossip['author']} said: \"{random_gossip['text']}\"?", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            else:
                await context.bot.edit_message_text("Nothing juicy to share yet.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            return

        # Sticker creation command
        if "sticker of" in prompt.lower():
            sticker_prompt = re.sub(r'(?i)make a sticker of\s*|sticker of\s*', '', prompt).strip()
            if not sticker_prompt:
                 await context.bot.edit_message_text("What kind of sticker? `/ai sticker of a happy cat`", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                 return
            await context.bot.edit_message_text(f"🎨 Creating sticker of `{sticker_prompt}`...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            image_bytes = await get_image_bytes_from_prompt(sticker_prompt)
            if image_bytes:
                sticker_file = process_image_for_sticker(image_bytes)
                if sticker_file:
                    try:
                        await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=sticker_file)
                        await thinking_message.delete()
                    except BadRequest as e:
                        logger.error(f"Failed to send sticker: {e}")
                        await context.bot.edit_message_text(f"Failed to send sticker: {e.message}", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                    return # Sticker sent or failed sending
                else:
                     await context.bot.edit_message_text("Couldn't process the image into a sticker.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            else:
                 await context.bot.edit_message_text("Failed to generate an image for the sticker.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            return # Sticker generation finished (success or fail)
        
        # --- NEW: Video Generation Command ---
        if "video of" in prompt.lower() or "make a video of" in prompt.lower():
            video_prompt = re.sub(r'(?i)(make a )?video of\s*', '', prompt).strip()
            if not video_prompt:
                await context.bot.edit_message_text("What kind of video? Usage: `/ai video of a cat chasing a laser`", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                return

            await context.bot.edit_message_text(f"🎬 Generating video: `{video_prompt}` (This may take a while)...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            video_bytes = await generate_video_from_text(video_prompt)

            if video_bytes:
                try:
                    # Sending the video
                    await context.bot.send_video(chat_id=update.effective_chat.id, video=video_bytes, caption=f"🎥 Video for: `{video_prompt}`", read_timeout=300, write_timeout=300, connect_timeout=300) # Add timeouts
                    await thinking_message.delete()
                except BadRequest as e:
                    logger.error(f"Failed to send video: {e}")
                    await context.bot.edit_message_text(f"Failed to send video: {e.message}", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
                except Exception as e:
                     logger.error(f"Unexpected error sending video: {e}")
                     await context.bot.edit_message_text("An unexpected error occurred sending the video.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            else:
                await context.bot.edit_message_text("Failed to generate the video.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            return # Video generation finished
        
        # Default action: Web Search + AI Answer
        await context.bot.edit_message_text("🔎 Searching the web...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        search_results = await execute_web_search(prompt)
        
        # Construct a more detailed prompt for the AI
        persona_prompt = "You are AI618, a witty and clever AI. Use your personality."
        final_prompt = (
            f"{persona_prompt} Answer the user's prompt based on the provided web search results. "
            f"If the search results seem irrelevant or failed ('Error:', 'No web results'), answer based on your own knowledge.\n\n"
            f"User Prompt: {prompt}\n\nWeb Search Results:\n{search_results}"
        )
        messages = [{"role": "system", "content": persona_prompt}, {"role": "user", "content": final_prompt}]
        
        await context.bot.edit_message_text("🧠 Thinking...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        response = await get_typegpt_response(messages)
        await send_final_response(update, context, response, thinking_message, prompt)

    except Exception as e:
        logger.error(f"Smart AI Handler failed catastrophically: {e}", exc_info=True)
        try:
            await context.bot.edit_message_text("An unexpected error occurred processing your request.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
        except BadRequest: pass # Ignore if original message deleted


async def master_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ensure message and text exist before proceeding
    if not update.message or not update.message.text:
        return

    chat_id = str(update.message.chat_id)
    session = trivia_sessions.get(chat_id)

    # --- LOCKDOWN MODE: If trivia is active, only game logic runs ---
    if session and session.get("state") in ["registering", "asking"]:
        await trivia_master_handler(update, context)
        return # Block all other AI features during the game.

    # --- Priority 2: Standard AI Replies & Mentions (only if no game is active) ---
    config = load_config()
    # Check if AI features are enabled for this chat before processing replies/mentions
    if config.get("ai_enabled_config", {}).get(chat_id, False):
        if update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id:
            await reply_handler(update, context)
            return

        if re.search(r'(?i)\bAI618\b', update.message.text):
            await name_mention_handler(update, context)
            return

    # --- Priority 3: Proactive & Background Tasks (run regardless of AI status for history, but check AI status for reactions) ---
    await proactive_reaction_handler(update, context) # This function checks AI status internally
    await history_capture_handler(update, context) # Always capture history


async def trivia_master_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handles player registration ('me', 'all in') during the registration phase."""
    chat_id = str(update.message.chat_id)
    session = trivia_sessions.get(chat_id)

    # Only act during registration state
    if not session or session.get("state") != "registering":
        return False

    user = update.message.from_user
    text = update.message.text.lower().strip()

    # Check if it's a reply to the registration message
    if update.message.reply_to_message and update.message.reply_to_message.message_id == session.get("registration_message_id"):
        if text == 'me':
            if user.id not in session["players"]:
                session["players"][user.id] = {"username": user.username, "first_name": user.first_name, "score": 0}
                await update.message.reply_text(f"{user.first_name} is in! ✅")
            else:
                await update.message.reply_text("You're already in!")
            return True # Message handled

        elif text == 'all in':
            if not session["players"]:
                await update.message.reply_text("We need at least one player to start!")
                return True # Message handled

            # Get player names for announcement
            player_list = []
            for p_data in session["players"].values():
                mention = f"@{p_data['username']}" if p_data['username'] else p_data['first_name']
                player_list.append(mention)

            await update.message.reply_text(f"Registration closed! Players: {', '.join(player_list)}. Let's begin!")
            # Delete registration message
            try: await context.bot.delete_message(chat_id, session["registration_message_id"])
            except BadRequest: pass
            
            # Start the game by asking the first question
            await ask_next_trivia_question(context, chat_id)
            return True # Message handled
            
    return False # Not a relevant registration message

async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure messages exist
    if not update.message or not update.message.text or not update.message.reply_to_message or not update.message.reply_to_message.text: return
    
    thinking_message = await update.message.reply_text("...")
    # Use a consistent persona prompt
    persona = "You are AI618, a witty and clever AI. Respond in character."
    messages = [
        {"role": "system", "content": persona},
        {"role": "assistant", "content": update.message.reply_to_message.text},
        {"role": "user", "content": update.message.text}
    ]
    response = await get_typegpt_response(messages)
    await send_final_response(update, context, response, thinking_message, "AI Reply")

async def name_mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return

    thinking_message = await update.message.reply_text("...")
    persona = "You are AI618, a witty and clever AI. The user mentioned your name. Respond in character."
    messages = [
        {"role": "system", "content": persona},
        {"role": "user", "content": update.message.text}
    ]
    response = await get_typegpt_response(messages)
    await send_final_response(update, context, response, thinking_message, "AI Mention")

async def proactive_reaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only react if AI is on for the group
    config = load_config()
    chat_id = str(update.message.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False): return
    if not update.message or not update.message.text: return

    if random.random() < 0.45: # Reaction probability
        emoji_str = await get_emoji_reaction(update.message.text)
        if emoji_str:
            try:
                await context.bot.set_message_reaction(chat_id=update.effective_chat.id, message_id=update.effective_message.id, reaction=[ReactionTypeEmoji(emoji_str)])
                logger.info(f"Reacted with {emoji_str} in chat {chat_id}")
            except BadRequest as e:
                # Ignore common harmless errors or permission issues silently
                if "MESSAGE_NOT_MODIFIED" not in e.message and "REACTION_INVALID" not in e.message and "USER_IS_BLOCKED" not in e.message and "chat not found" not in e.message:
                    logger.warning(f"Failed to set reaction: {e.message}")
            except Exception as e:
                 logger.error(f"Unexpected error setting reaction: {e}")

async def history_capture_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure message and text exist
    if not update.message or not update.message.text: return

    chat_id = update.message.chat_id
    history = chat_histories.setdefault(chat_id, deque(maxlen=30)) # Store last 30 messages
    history.append(f"{update.message.from_user.first_name}: {update.message.text}")
    
    # Schedule random chat only if AI is enabled AND random chat is enabled for this group
    config = load_config()
    chat_id_str = str(chat_id)
    if config.get("ai_enabled_config", {}).get(chat_id_str, False) and \
       config.get("random_chat_config", {}).get(chat_id_str, True): # Default random ON if not set
        # Check if job_queue is available before using it
        if not context.job_queue:
            logger.warning("Job queue is None in history_capture_handler, cannot schedule random chat")
            return
        
        # Check existing jobs for this chat
        current_jobs = context.job_queue.get_jobs_by_name(f"random_chat_{chat_id}")
        if not current_jobs: # Only schedule if no job exists
             context.job_queue.run_once(random_chat_callback, random.uniform(300, 600), data={'chat_id': chat_id}, name=f"random_chat_{chat_id}")
             # active_random_jobs isn't strictly needed now if we check get_jobs_by_name
             logger.info(f"Scheduled random chat job for chat_id: {chat_id}")

async def random_chat_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data['chat_id']
    # No need for active_random_jobs tracking if we check get_jobs_by_name before scheduling

    config = load_config()
    chat_id_str = str(chat_id)
    # Double check settings before sending
    if not config.get("ai_enabled_config", {}).get(chat_id_str, False) or \
       not config.get("random_chat_config", {}).get(chat_id_str, True):
        logger.info(f"Random chat skipped for {chat_id} due to settings.")
        return

    if chat_id in chat_histories and len(chat_histories[chat_id]) > 5:
        transcript = "\n".join(chat_histories[chat_id])
        prompt = (
            "You are AI618, a witty and clever AI in a group chat. Based on the recent chat transcript, "
            "inject ONE short, engaging, and in-character message (like a witty observation, a sharp question, "
            "or a relatable comment). Use Hinglish/English and abbreviations naturally. NEVER reveal you are an AI. "
            "Keep it under 15 words.\n\n"
            f"--- Transcript ---\n{transcript}\n\n--- Your Message ---"
        )
        messages = [{"role": "system", "content": prompt}]
        response = await get_typegpt_response(messages)
        if response:
            try:
                await context.bot.send_message(chat_id=chat_id, text=response)
                chat_histories[chat_id].clear() # Clear history after commenting
            except BadRequest as e:
                logger.error(f"Failed to send random chat message: {e}")
        else:
             logger.warning(f"Random chat AI failed to generate response for chat {chat_id}")
    else:
        logger.info(f"Skipping random chat for {chat_id}, not enough history.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure message exists
    if not update.message: return
    help_text = (
        "**AI Features** (`/ai` prefix for most)\n"
        "`start trivia on [topic] [num]Q` - Start a trivia game (Admin)\n"
        "`stop trivia` - Stop the current game (Admin)\n"
        "`remember this` (Reply to msg) - Save a message to gossip memory\n"
        "`gossip` - Recall a random saved message\n"
        "`sticker of [prompt]` - Create an AI sticker\n"
        "`video of [prompt]` - Create an AI video (Experimental)\n"
        "`[Your question]` - Get AI answer (uses web search by default)\n\n"
        "**Other Commands**\n"
        "`/audio` - Toggle voice responses ON/OFF (Admin)\n"
        "`/audio list` - Show available TTS voices\n"
        "`/audio [voice]` - Set TTS voice (e.g., guy, davis, jenny)\n"
        "`/react` (Reply to msg) - Force AI reaction\n"
        "`/help` - Show this message\n"
        "`/chem [SMILES]` - Draw chemical structure\n"
        "`/tex [LaTeX]` - Render LaTeX expression\n"
        "`/chatid` - Get current chat ID\n\n"
        "**Memory**\n"
        "`/remember topic = fact`\n"
        "`/recall [topic]` (Leave blank for list)\n"
        "`/forget [topic]`\n\n"
        "**Admin Settings**\n"
        "`/boton`, `/botoff`, `/aistatus` - AI features ON/OFF\n"
        "`/randomon`, `/randomoff`, `/randomstatus` - Proactive chat ON/OFF\n"
        "`/testrandom` - Trigger proactive chat now\n"
        "`/on`, `/off` - Moderation commands ON/OFF\n"
        "`/time HH:MM` - Set daily reminder time (IST)\n\n"
        "**Moderation** (Requires Mod ON & Admin)\n"
        "`/ban`, `/mute`, `/unmute` (Reply to user)\n"
        "`/delete` (Reply to message)\n"
        "`/lock`, `/unlock` (Chat permissions)"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def force_react_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure message exists
    if not update.message: return
    replied_message = update.message.reply_to_message
    if not replied_message or not replied_message.text:
        await update.message.reply_text("Reply to a text message to react.")
        return
    emoji_str = await get_emoji_reaction(replied_message.text)
    if emoji_str:
        try:
            await context.bot.set_message_reaction(chat_id=update.effective_chat.id, message_id=replied_message.message_id, reaction=[ReactionTypeEmoji(emoji_str)])
            # Delete the command message
            try: await update.message.delete()
            except BadRequest: pass
        except BadRequest as e:
            logger.warning(f"Failed to force reaction: {e.message}")
            # Don't send error message to user, just log

async def toggle_audio_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Toggle audio mode or change voice.
    Usage: 
        /audio - Toggle audio mode on/off
        /audio <voice_name> - Set voice and enable audio mode
        /audio list - Show available voices
    """
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context):
         await update.message.reply_text("Only admins can toggle audio mode.")
         return
    
    chat_id = str(update.message.chat_id)
    config = load_config()
    
    # Handle voice listing
    if context.args and context.args[0].lower() == "list":
        voice_list = "\n".join([f"• `{name}` - {voice}" for name, voice in AVAILABLE_TTS_VOICES.items()])
        current_voice = config.get("tts_voice_config", {}).get(chat_id, DEFAULT_TTS_VOICE)
        await update.message.reply_text(
            f"**Available TTS Voices:**\n\n{voice_list}\n\n"
            f"**Current voice:** `{current_voice}`\n\n"
            f"Use `/audio <voice_name>` to change voice.",
            parse_mode='Markdown'
        )
        return
    
    # Handle voice change
    if context.args:
        voice_name = context.args[0].lower()
        if voice_name in AVAILABLE_TTS_VOICES:
            selected_voice = AVAILABLE_TTS_VOICES[voice_name]
            config.setdefault("tts_voice_config", {})[chat_id] = selected_voice
            config.setdefault("audio_mode_config", {})[chat_id] = True
            save_config(config)
            await update.message.reply_text(
                f"🎤 Voice set to **{voice_name}** (`{selected_voice}`) and audio mode enabled.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ Voice '{voice_name}' not found. Use `/audio list` to see available voices.",
                parse_mode='Markdown'
            )
        return
    
    # Toggle audio mode
    is_enabled = config.setdefault("audio_mode_config", {}).get(chat_id, False)
    config["audio_mode_config"][chat_id] = not is_enabled
    save_config(config)
    status = "ON" if not is_enabled else "OFF"
    current_voice = config.get("tts_voice_config", {}).get(chat_id, DEFAULT_TTS_VOICE)
    await update.message.reply_text(
        f"🎤 Audio mode is now **{status}**.\n"
        f"Current voice: `{current_voice}`\n\n"
        f"Use `/audio <voice>` to change voice or `/audio list` to see options.",
        parse_mode='Markdown'
    )

# --- Other Command Handlers ---

async def chem_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    smiles = " ".join(context.args)
    if not smiles:
        await update.message.reply_text("Provide a SMILES string. Usage: `/chem CCO`")
        return
    mol = await asyncio.to_thread(Chem.MolFromSmiles, smiles) # Run RDKit in thread
    if mol is None:
        await update.message.reply_text("Invalid SMILES string.")
        return
    try:
        # Run drawing in thread as it might be CPU intensive
        def draw_molecule(mol_obj):
             drawer = rdMolDraw2D.MolDraw2DC(300, 300)
             drawer.DrawMolecule(mol_obj)
             drawer.FinishDrawing()
             return drawer.GetDrawingText()

        png_data = await asyncio.to_thread(draw_molecule, mol)

        png_buffer = io.BytesIO(png_data)
        await update.message.reply_photo(photo=InputFile(png_buffer, filename='molecule.png'), caption=f"`{smiles}`", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"RDKit chem handler failed: {e}")
        await update.message.reply_text("Error generating molecule image.")

async def latex_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    latex_code = " ".join(context.args)
    if not latex_code:
        await update.message.reply_text("Provide a LaTeX expression. Usage: `/tex E = mc^2`")
        return
    try:
        url = f"https://latex.codecogs.com/png.latex?%5Cdpi{{300}}%20{httpx.utils.quote(latex_code)}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0) # Increased timeout
            if response.status_code == 200:
                await update.message.reply_photo(photo=response.content, caption=f"`{latex_code}`", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"Failed to render LaTeX (Status: {response.status_code}). Check syntax?")
    except httpx.TimeoutException:
         await update.message.reply_text("LaTeX rendering service timed out.")
    except Exception as e:
        logger.error(f"LaTeX handler failed: {e}")
        await update.message.reply_text("Error rendering LaTeX.")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    await update.message.reply_text(f"This Chat ID is: `{update.message.chat_id}`", parse_mode='Markdown')

async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    text = " ".join(context.args)
    if '=' not in text:
        await update.message.reply_text("Usage: `/remember topic = fact`")
        return
    topic, fact = [x.strip() for x in text.split('=', 1)]
    if not topic or not fact:
        await update.message.reply_text("Both topic and fact are required.")
        return
    memory = load_memory()
    memory[topic.lower()] = fact
    save_memory(memory)
    await update.message.reply_text(f"👍 Okay, remembered that '{topic}' is '{fact}'.")

async def recall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not context.args:
        memory = load_memory()
        if not memory:
            await update.message.reply_text("I haven't remembered anything yet.")
            return
        topics = ", ".join(memory.keys())
        await update.message.reply_text(f"Topics I remember: {topics}")
        return
    topic = " ".join(context.args).lower()
    memory = load_memory()
    fact = memory.get(topic)
    if fact:
        await update.message.reply_text(f"'{topic}': {fact}")
    else:
        await update.message.reply_text(f"I don't remember anything about '{topic}'.")

async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not context.args:
        await update.message.reply_text("What should I forget? Usage: `/forget topic`")
        return
    topic = " ".join(context.args).lower()
    memory = load_memory()
    if topic in memory:
        del memory[topic]
        save_memory(memory)
        await update.message.reply_text(f"👌 Okay, forgot about '{topic}'.")
    else:
        await update.message.reply_text(f"I didn't know anything about '{topic}' anyway.")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    chat_id = update.message.chat_id
    if chat_id not in chat_histories or len(chat_histories[chat_id]) < 3: # Lowered threshold
        await update.message.reply_text("Not enough recent chat history to summarize.")
        return
    transcript = "\n".join(chat_histories[chat_id])
    prompt = f"Summarize the following recent group chat transcript concisely in a few bullet points:\n\n{transcript}"
    thinking_message = await update.message.reply_text("Summarizing...")
    summary = await get_typegpt_response([{"role": "system", "content": "You summarize chat logs into key points."}, {"role": "user", "content": prompt}])
    await send_final_response(update, context, summary, thinking_message, "Chat Summary")

async def studypoll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context):
        await update.message.reply_text("Only admins can create polls.")
        return
    try:
        # Use shlex to handle quotes correctly
        args = shlex.split(" ".join(context.args))
        if len(args) < 3 or len(args) > 11: # Question + 2-10 options
            await update.message.reply_text('Usage: /studypoll "Question" "Option 1" "Option 2" ... (Max 10 options)')
            return
        question = args[0]
        options = args[1:]
        await context.bot.send_poll(chat_id=update.effective_chat.id, question=question, options=options, is_anonymous=False)
    except ValueError as e: # Catch shlex errors
         await update.message.reply_text(f"Error parsing arguments (check your quotes?): {e}")
    except Exception as e:
        await update.message.reply_text(f"Error creating poll: {e}")

async def aipoll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    await update.message.reply_text("Use `/ai make a poll about [topic]` instead.")

async def web_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    await update.message.reply_text("Use `/ai [your query]` for web search.")

async def nanoedit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config()
    chat_id = str(update.message.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False):
        await update.message.reply_text("AI is off for this group.")
        return

    replied_message = update.message.reply_to_message
    if not (replied_message and replied_message.photo):
        await update.message.reply_text("Reply to an image with /nanoedit to use this command.")
        return

    prompt = " ".join(context.args)
    if not prompt: prompt = "Describe this image."

    thinking_message = await update.message.reply_text("Processing image with Nano...")

    try:
        photo_file = await replied_message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
        
        # --- PRIMARY: OpenRouter ---
        try:
            logger.info("Trying Primary Nanoedit API: OpenRouter")
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost", "X-Title": "AI618 Bot"}
            payload = {"model": "google/gemini-2.5-flash-image-preview:free", "messages": messages, "max_tokens": 4096}
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status() # Raise error for bad status
            result = response.json()
            message_content = result.get("choices", [{}])[0].get("message", {})
            # Check for 'image' field in OpenRouter response structure
            images_output = message_content.get("image") or message_content.get("images") # Adapt to potential variations

            if images_output:
                # Handle potential list or single object
                if isinstance(images_output, list):
                    image_data = images_output[0] if images_output else None
                else:
                    image_data = images_output
                
                if image_data:
                    image_data_url = image_data.get("image_url", {}).get("url")
                    if image_data_url and "base64," in image_data_url:
                        base64_string = image_data_url.split(',', 1)[1]
                        image_bytes = base64.b64decode(base64_string)
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=f"🖼️ Result: `{prompt}`", parse_mode='Markdown')
                        await thinking_message.delete()
                        return
            # If no image, check for text content
            text_response = message_content.get("content")
            if text_response:
                 await send_final_response(update, context, text_response, thinking_message, prompt)
                 return
            raise ValueError("Primary API returned no image or text.")

        except Exception as e:
            logger.error(f"Nanoedit Primary API (OpenRouter) failed: {e}. Trying text fallback.")
            await context.bot.edit_message_text("Image edit failed, trying description...", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
            # --- FALLBACK: Text-based vision ---
            text_response = await get_typegpt_gemini_vision_response(messages) # Or Baidu
            if not text_response:
                text_response = await get_baidu_ernie_vision_response(messages)
            
            if text_response:
                 await send_final_response(update, context, text_response, thinking_message, prompt)
            else:
                 await context.bot.edit_message_text("All fallbacks failed.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)
    
    except Exception as e:
        logger.error(f"Nanoedit handler failed catastrophically: {e}")
        await context.bot.edit_message_text("Command Failed.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)


async def askit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config()
    chat_id = str(update.message.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False):
        await update.message.reply_text("AI is off for this group.")
        return

    replied_message = update.message.reply_to_message
    if not (replied_message and replied_message.photo):
        await update.message.reply_text("Reply to an image with /askit.")
        return

    prompt = " ".join(context.args) or "Describe this image in detail."
    thinking_message = await update.message.reply_text("Analyzing image...")

    try:
        photo_file = await replied_message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
        
        # Vision Model Fallback Chain
        response_text = await get_typegpt_gemini_vision_response(messages)
        if not response_text:
            logger.warning("Gemini Pro vision failed. Trying Baidu Ernie.")
            response_text = await get_baidu_ernie_vision_response(messages)
        # Add more vision fallbacks if needed

        if response_text:
            await send_final_response(update, context, response_text, thinking_message, prompt)
        else:
            await context.bot.edit_message_text("All vision models failed.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)

    except Exception as e:
        logger.error(f"Askit handler failed: {e}")
        await context.bot.edit_message_text("Image analysis failed.", chat_id=update.effective_chat.id, message_id=thinking_message.message_id)

async def simple_ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    # Keep this for backward compatibility or simpler tasks if needed
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt.")
        return
    thinking_message = await update.message.reply_text("Thinking...")
    messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    response = await get_typegpt_response(messages) # Use the main chain
    await send_final_response(update, context, response, thinking_message, prompt)
    
# --- Settings and Moderation Command Handlers ---

async def turn_ai_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id)
    config = load_config(); config.setdefault("ai_enabled_config", {})[chat_id] = True; save_config(config)
    await update.message.reply_text("✅ AI features **ON**.", parse_mode='Markdown')

async def turn_ai_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id); config = load_config()
    config.setdefault("ai_enabled_config", {})[chat_id] = False; save_config(config)
    await update.message.reply_text("❌ AI features **OFF**.", parse_mode='Markdown')

async def check_ai_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id); config = load_config()
    status = "ON" if config.get("ai_enabled_config", {}).get(chat_id, False) else "OFF"
    await update.message.reply_text(f"ℹ️ AI features are **{status}**.", parse_mode='Markdown')

async def turn_random_chat_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id); config = load_config()
    config.setdefault("random_chat_config", {})[chat_id] = True; save_config(config)
    await update.message.reply_text("✅ Random chat **ON**.", parse_mode='Markdown')

async def turn_random_chat_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id); config = load_config()
    config.setdefault("random_chat_config", {})[chat_id] = False; save_config(config)
    await update.message.reply_text("❌ Random chat **OFF**.", parse_mode='Markdown')

async def check_random_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    chat_id = str(update.message.chat_id); config = load_config()
    status = "ON" if config.get("random_chat_config", {}).get(chat_id, True) else "OFF" # Default ON
    await update.message.reply_text(f"ℹ️ Random chat is **{status}**.", parse_mode='Markdown')

async def test_random_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    
    if not context.job_queue:
        await update.message.reply_text("⚠️ Job queue not available.")
        logger.warning("Job queue is None in test_random_handler")
        return
        
    await update.message.reply_text("Triggering random chat logic now...")
    # Schedule immediately
    context.job_queue.run_once(random_chat_callback, 0, data={"chat_id": update.message.chat_id})

async def turn_moderation_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    config = load_config(); config["moderation_enabled"] = True; save_config(config)
    await update.message.reply_text("✅ Moderation commands **ON**.", parse_mode='Markdown')

async def turn_moderation_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): return
    config = load_config(); config["moderation_enabled"] = False; save_config(config)
    await update.message.reply_text("❌ Moderation commands **OFF**.", parse_mode='Markdown')

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config()
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to ban."); return
    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.message.chat_id, target_user.id)
        await update.message.reply_text(f"Banned {target_user.first_name}.")
    except Exception as e: await update.message.reply_text(f"Failed to ban: {e}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to mute."); return
    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(update.message.chat_id, target_user.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"Muted {target_user.first_name}.")
    except Exception as e: await update.message.reply_text(f"Failed to mute: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to unmute."); return
    target_user = update.message.reply_to_message.from_user
    try:
        # Restore default permissions (adjust if your group has specific defaults)
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True, can_send_polls=True, can_invite_users=True) # Common defaults
        await context.bot.restrict_chat_member(update.message.chat_id, target_user.id, perms)
        await update.message.reply_text(f"Unmuted {target_user.first_name}.")
    except Exception as e: await update.message.reply_text(f"Failed to unmute: {e}")

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to delete."); return
    try:
        await context.bot.delete_message(update.message.chat_id, update.message.reply_to_message.message_id)
        # Delete the command message too for cleanliness
        try: await update.message.delete()
        except BadRequest: pass # Ignore if already gone
    except Exception as e: await update.message.reply_text(f"Failed to delete: {e}")

async def lock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    try:
        await context.bot.set_chat_permissions(update.message.chat_id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text("🔒 Chat locked.")
    except Exception as e: await update.message.reply_text(f"Failed to lock: {e}")

async def unlock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await update.message.reply_text("Mod commands off."); return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    try:
        # Restore default permissions (adjust if needed)
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True)
        await context.bot.set_chat_permissions(update.message.chat_id, perms)
        await update.message.reply_text("🔓 Chat unlocked.")
    except Exception as e: await update.message.reply_text(f"Failed to unlock: {e}")

async def set_reminder_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not await is_user_admin(update.message.chat_id, update.message.from_user.id, context): await update.message.reply_text("Admins only."); return
    if not context.args: await update.message.reply_text("Usage: /time HH:MM (24-hour IST)"); return
    try:
        new_time_str = context.args[0]
        new_time_obj = datetime.strptime(new_time_str, "%H:%M").time()
        config = load_config(); config["reminder_time"] = new_time_str; save_config(config)
        
        # Reschedule job - with null check
        if not context.job_queue:
            await update.message.reply_text("⚠️ Job queue not available. Time saved but job not rescheduled.")
            logger.warning("Job queue is None in set_reminder_time_handler")
            return
            
        current_jobs = context.job_queue.get_jobs_by_name("daily_reminder")
        for job in current_jobs: job.schedule_removal()
        reminder_time = time(hour=new_time_obj.hour, minute=new_time_obj.minute, tzinfo=pytz.timezone('Asia/Kolkata'))
        context.job_queue.run_daily(send_daily_reminder, time=reminder_time, name="daily_reminder")
        await update.message.reply_text(f"✅ Reminder time updated to {new_time_str} IST.")
    except ValueError: await update.message.reply_text("Invalid time format. Use HH:MM.")
    except Exception as e: 
        logger.error(f"Error in set_reminder_time_handler: {e}", exc_info=True)
        await update.message.reply_text(f"Error setting time: {e}")

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    if TARGET_CHAT_ID == 0: logger.warning("TARGET_CHAT_ID not set or invalid."); return
    try:
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist).date()
        message_lines = []
        days_mains = (JEE_MAINS_DATE - today).days
        days_adv = (JEE_ADV_DATE - today).days

        if days_mains >= 0: message_lines.append(f"⏳ **{days_mains} DAYS LEFT FOR JEE MAINS!**")
        if days_adv >= 0: message_lines.append(f"⏳ **{days_adv} DAYS LEFT FOR JEE ADVANCED!**")
        if MOTIVATIONAL_QUOTES: message_lines.append(f"\n✨ \"_{random.choice(MOTIVATIONAL_QUOTES)}_\"")
        
        if message_lines: # Only send if there's something to say
            message = "\n".join(message_lines)
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=message, parse_mode='Markdown')
            logger.info(f"Sent daily reminder to {TARGET_CHAT_ID}")
        else:
            logger.info("No relevant dates left for daily reminder.")
            # Optionally remove the job if no dates are left
            # context.job.schedule_removal()
    except Exception as e: logger.error(f"Failed to send daily reminder: {e}")

# --- Main Function ---
def main() -> None:
    # Ensure necessary directories/files exist (optional, helps first run)
    if not os.path.exists(CONFIG_FILE): save_config({})
    if not os.path.exists(MEMORY_FILE): save_memory({})
    if not os.path.exists(GOSSIP_FILE): save_gossip({})

    application = Application.builder().token(BOT_TOKEN).build()
    
    # --- Register ALL Handlers ---
    handlers = [
        # Core Commands
        CommandHandler("start", help_command),
        CommandHandler("help", help_command),
        CommandHandler("ai", smart_ai_handler), # Handles trivia, gossip, stickers, web search

        # Utility Commands
        CommandHandler("react", force_react_command),
        CommandHandler("audio", toggle_audio_mode_handler),
        CommandHandler("chem", chem_handler),
        CommandHandler("tex", latex_handler),
        CommandHandler("chatid", get_chat_id),
        CommandHandler("summarize", summarize_command),
        CommandHandler("studypoll", studypoll_command), # Manual poll creation

        # Memory Commands
        CommandHandler("remember", remember_command),
        CommandHandler("recall", recall_command),
        CommandHandler("forget", forget_command),

        # Image Commands
        CommandHandler("nanoedit", nanoedit_handler),
        CommandHandler("askit", askit_handler),
        # CommandHandler("image", image_generation_handler), # Can be re-added if direct access needed

        # Settings Commands (Admin)
        CommandHandler("boton", turn_ai_on), CommandHandler("botoff", turn_ai_off),
        CommandHandler("aistatus", check_ai_status),
        CommandHandler("randomon", turn_random_chat_on), CommandHandler("randomoff", turn_random_chat_off),
        CommandHandler("randomstatus", check_random_status),
        CommandHandler("testrandom", test_random_handler),
        CommandHandler("on", turn_moderation_on), CommandHandler("off", turn_moderation_off),
        CommandHandler("time", set_reminder_time_handler),

        # Moderation Commands (Admin & Mod Enabled)
        CommandHandler("ban", ban_user), CommandHandler("mute", mute_user),
        CommandHandler("unmute", unmute_user), CommandHandler("delete", delete_message),
        CommandHandler("lock", lock_chat), CommandHandler("unlock", unlock_chat),

        # Optional simple AI handler
        CommandHandler(["ai1", "ai618"], simple_ai_handler),

        # Master handler for all non-command text (handles trivia, replies, mentions, reactions, history)
        MessageHandler(filters.TEXT & ~filters.COMMAND, master_text_handler)
    ]
    application.add_handlers(handlers)
    
    # --- Schedule Daily Reminder (AFTER application is built and handlers are registered) ---
    config = load_config()
    reminder_time_str = config.get("reminder_time", "04:00")
    try:
        hour, minute = map(int, reminder_time_str.split(':'))
        # Access job_queue AFTER application is built and handlers are added
        job_queue = application.job_queue
        if job_queue:
            reminder_time = time(hour=hour, minute=minute, tzinfo=pytz.timezone('Asia/Kolkata'))
            # Add the job if it doesn't exist already
            existing_jobs = job_queue.get_jobs_by_name("daily_reminder")
            if not existing_jobs:
                job_queue.run_daily(send_daily_reminder, time=reminder_time, name="daily_reminder")
                logger.info(f"Daily reminder job scheduled for {reminder_time_str} IST.")
            else:
                logger.info("Daily reminder job already scheduled.")
        else:
            logger.warning("Job queue is not available. Daily reminder not scheduled.")
    except ValueError:
        logger.error(f"Invalid reminder time format: {reminder_time_str}. Reminder not scheduled.")
    except Exception as e:
        logger.error(f"Error scheduling daily reminder: {e}", exc_info=True)

    # Start the keep-alive server thread
    keep_alive()
    
    logger.info("Bot is running...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES) # Process all update types

if __name__ == '__main__':
    main()
