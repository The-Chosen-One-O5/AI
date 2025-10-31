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

# --- Library Imports ---
import replicate
import emoji
from openai import AsyncOpenAI, OpenAIError
from cerebras.cloud.sdk import Cerebras
from groq import AsyncGroq
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D
from PIL import Image
from bs4 import BeautifulSoup
from telegraph import Telegraph

# --- Telethon Imports ---
from telethon import TelegramClient, events, types, functions, errors
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, ChannelParticipantsAdmins
from telethon.tl.functions.messages import SendReactionRequest

# NOTE: Call features are handled by separate Ray userbot deployment

# --- Configuration (using Environment Variables) ---
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables!")
    exit(1)

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
#   - Replicate: minimax/speech-02-hd
#
# Image Generation:
#   - Infip API: Qwen model
#
# Note: Update these models in their respective functions if providers deprecate them.
# Check deprecation notices: https://console.groq.com/docs/deprecations

# Validate essential credentials
if not API_ID:
    print("FATAL ERROR: API_ID environment variable not set!")
    print("Get your API credentials from https://my.telegram.org")
    exit()
if not API_HASH:
    print("FATAL ERROR: API_HASH environment variable not set!")
    print("Get your API credentials from https://my.telegram.org")
    exit()

# Setup optional API tokens
if REPLICATE_API_KEY:
    os.environ['REPLICATE_API_TOKEN'] = REPLICATE_API_KEY # Replicate specifically needs this env var
else:
    print("WARNING: REPLICATE_API_KEY not set. Audio mode will fail.")


# --- State Management ---
chat_histories = {}
active_random_jobs = set()
trivia_sessions = {}

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

# --- Telethon Client Initialization ---
client = TelegramClient('bot_session', API_ID, API_HASH)

# ================== TELETHON CONTEXT WRAPPER ==================
# Provides python-telegram-bot-like interface using Telethon

class BotContext:
    """Context wrapper providing bot functionality"""
    def __init__(self, client):
        self.client = client
        self.bot = BotAPI(client)
        self.job_queue = JobQueue(client)
        self.id = None
    async def initialize(self):
        me = await self.client.get_me()
        self.id = me.id
        self.bot.id = me.id

class BotAPI:
    """Bot API wrapper mimicking python-telegram-bot"""
    def __init__(self, client):
        self.client = client
        self.id = None
    async def send_message(self, chat_id, text, parse_mode=None, reply_to_message_id=None):
        pm = 'md' if parse_mode == 'Markdown' else ('html' if parse_mode == 'HTML' else None)
        return await self.client.send_message(chat_id, text, parse_mode=pm, reply_to=reply_to_message_id)
    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None, reply_to_message_id=None):
        pm = 'md' if parse_mode == 'Markdown' else ('html' if parse_mode == 'HTML' else None)
        return await self.client.send_file(chat_id, photo, caption=caption, parse_mode=pm, reply_to=reply_to_message_id)
    async def send_voice(self, chat_id, voice, caption=None, reply_to_message_id=None):
        return await self.client.send_file(chat_id, voice, voice_note=True, caption=caption, reply_to=reply_to_message_id)
    async def send_video(self, chat_id, video, caption=None, parse_mode=None, reply_to_message_id=None, **kwargs):
        pm = 'md' if parse_mode == 'Markdown' else None
        return await self.client.send_file(chat_id, video, caption=caption, parse_mode=pm, reply_to=reply_to_message_id)
    async def send_sticker(self, chat_id, sticker):
        return await self.client.send_file(chat_id, sticker)
    async def send_poll(self, chat_id, question, options, type='quiz', correct_option_id=None, is_anonymous=False, open_period=None):
        quiz = (type == 'quiz')
        return await self.client.send_message(chat_id, question, poll=types.InputMediaPoll(
            poll=types.Poll(id=0, question=question,
                          answers=[types.PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(options)],
                          closed=False, public_voters=not is_anonymous, quiz=quiz, close_period=open_period),
            correct_answers=[bytes([correct_option_id])] if quiz and correct_option_id is not None else None))
    async def edit_message_text(self, text, chat_id, message_id, parse_mode=None):
        pm = 'md' if parse_mode == 'Markdown' else ('html' if parse_mode == 'HTML' else None)
        return await self.client.edit_message(chat_id, message_id, text, parse_mode=pm)
    async def delete_message(self, chat_id, message_id):
        return await self.client.delete_messages(chat_id, [message_id])
    async def get_chat_administrators(self, chat_id):
        try:
            return await self.client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
        except: return []
    async def set_message_reaction(self, chat_id, message_id, reaction):
        emoji_reaction = reaction[0].emoji if hasattr(reaction[0], 'emoji') else str(reaction[0])
        await self.client(SendReactionRequest(peer=chat_id, msg_id=message_id,
                                            reaction=[types.ReactionEmoji(emoticon=emoji_reaction)]))
    async def ban_chat_member(self, chat_id, user_id):
        await self.client(EditBannedRequest(channel=chat_id, participant=user_id,
            banned_rights=ChatBannedRights(until_date=None, view_messages=True)))
    async def restrict_chat_member(self, chat_id, user_id, permissions):
        await self.client(EditBannedRequest(channel=chat_id, participant=user_id,
            banned_rights=ChatBannedRights(until_date=None,
                send_messages=not getattr(permissions, 'can_send_messages', True),
                send_media=not getattr(permissions, 'can_send_media_messages', True),
                send_stickers=not getattr(permissions, 'can_send_other_messages', True),
                send_polls=not getattr(permissions, 'can_send_polls', True),
                invite_users=not getattr(permissions, 'can_invite_users', True))))
    async def set_chat_permissions(self, chat_id, permissions):
        await self.client.edit_permissions(chat_id,
            send_messages=getattr(permissions, 'can_send_messages', True),
            send_media=getattr(permissions, 'can_send_media_messages', True),
            send_polls=getattr(permissions, 'can_send_polls', True),
            invite_users=getattr(permissions, 'can_invite_users', True))

class JobQueue:
    """Job queue using asyncio"""
    def __init__(self, client):
        self.client = client
        self.jobs = {}
    def run_once(self, callback, when, data=None, name=None):
        async def job_wrapper():
            await asyncio.sleep(when)
            job_data = type('JobData', (), {'data': data, 'name': name})()
            context_obj = type('Context', (), {'job': job_data, 'bot': global_context.bot})()
            await callback(context_obj)
            if name and name in self.jobs: del self.jobs[name]
        task = asyncio.create_task(job_wrapper())
        if name: self.jobs[name] = task
        return task
    def run_daily(self, callback, time, data=None, name=None):
        async def daily_wrapper():
            while True:
                now = datetime.now(time.tzinfo)
                target = now.replace(hour=time.hour, minute=time.minute, second=0, microsecond=0)
                if target <= now:
                    from datetime import timedelta
                    target = target + timedelta(days=1)
                delay = (target - now).total_seconds()
                await asyncio.sleep(delay)
                job_data = type('JobData', (), {'data': data, 'name': name})()
                context_obj = type('Context', (), {'job': job_data, 'bot': global_context.bot})()
                await callback(context_obj)
        task = asyncio.create_task(daily_wrapper())
        if name: self.jobs[name] = task
        return task
    def get_jobs_by_name(self, name):
        return [self.jobs[name]] if name in self.jobs else []

class ChatPermissions:
    """Chat permissions"""
    def __init__(self, can_send_messages=False, can_send_media_messages=False, 
                 can_send_polls=False, can_send_other_messages=False, 
                 can_add_web_page_previews=False, can_invite_users=False):
        self.can_send_messages = can_send_messages
        self.can_send_media_messages = can_send_media_messages
        self.can_send_polls = can_send_polls
        self.can_send_other_messages = can_send_other_messages
        self.can_add_web_page_previews = can_add_web_page_previews
        self.can_invite_users = can_invite_users

class ReactionTypeEmoji:
    """Reaction emoji"""
    def __init__(self, emoji):
        self.emoji = emoji

global_context = None

# ================== END CONTEXT WRAPPER ==================


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
            "audio_mode_config": {}
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

async def delete_message_callback(context):
    """Callback to delete a message after delay"""
    job = context.job
    try:
        await global_context.bot.delete_message(chat_id=job.data['chat_id'], message_id=job.data['message_id'])
    except errors.RPCError: pass # Ignore if message already deleted

async def send_deletable_message(chat_id: int, text: str, reply_to_message_id: int = None):
    """Send a message that will be deleted after 120 seconds"""
    try:
        sent_message = await global_context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id, parse_mode='Markdown')
        global_context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.id})
        return sent_message
    except errors.RPCError as e:
        logger.error(f"Failed to send deletable message (Markdown error?): {e}")
        try:
            sent_message = await global_context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)
            global_context.job_queue.run_once(delete_message_callback, 120, data={'chat_id': chat_id, 'message_id': sent_message.id})
            return sent_message
        except Exception as e2:
            logger.error(f"Failed to send deletable message as plain text: {e2}")
            return None # Indicate failure


async def generate_audio_from_text(text: str) -> bytes | None:
    if not REPLICATE_API_KEY:
        logger.error("Replicate API key not configured. Cannot generate audio.")
        return None
    cleaned_text = re.sub(r'[*_`]', '', text) # Remove markdown for cleaner TTS
    if not cleaned_text.strip(): return None
    try:
        logger.info("Generating audio with Replicate...")
        input_params = {
            "text": cleaned_text,
            "emotion": "happy", # You could potentially vary this based on AI response sentiment
            "voice_id": "Friendly_Person", # Or choose another voice
            "language_boost": "English", # Adjust if needed
            "english_normalization": True
        }
        output = await asyncio.to_thread(
            replicate.run,
            "minimax/speech-02-hd:408e2f3d6f1f0a149b5c777d8a0f5a7707e99741a4a15995f532b13c77e779a1", # Use full model identifier
            input=input_params
        )

        if not output:
            logger.error("Replicate API did not return output.")
            return None
        output_url = output 

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(output_url)
            if response.status_code == 200:
                logger.info("Successfully generated and downloaded audio.")
                return response.content
            else:
                logger.error(f"Failed to download audio from Replicate URL: Status {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Failed to generate audio with Replicate: {e}")
        return None

async def generate_video_from_text(prompt: str) -> bytes | None:
    """Generates video from text using the Samurai API."""
    if not SAMURAI_API_KEY:
        logger.error("Samurai API key not configured. Cannot generate video.")
        return None

    logger.info(f"Generating video with Samurai API for prompt: {prompt}")
    
    api_urls = [
        "https://samuraiapi.in/v1/videos",
        "https://samuraiapi.in/videos",
        "https://amuraiapi.in/v1/videos/generations"
    ]
    
    headers = {
        "Authorization": f"Bearer {SAMURAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "wan-ai-wan2.1-t2v-14b",
        "prompt": prompt,
        "n": 1
    }

    for api_url in api_urls:
        try:
            logger.info(f"Trying endpoint: {api_url}")
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
                response = await client.post(api_url, headers=headers, json=payload)
                
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {response.headers}")
                logger.info(f"Response body preview: {response.text[:500]}")

                if response.status_code == 200:
                    result_data = response.json().get("data")
                    if result_data and isinstance(result_data, list) and len(result_data) > 0:
                        video_url = result_data[0].get("url")
                        if video_url:
                            logger.info(f"Downloading generated video from: {video_url}")
                            video_response = await client.get(video_url, timeout=300.0)
                            video_response.raise_for_status()
                            logger.info("Video downloaded successfully.")
                            return video_response.content
                    
                    logger.warning(f"Unexpected response structure from {api_url}")
                    continue
                    
                elif response.status_code == 404:
                    logger.warning(f"Endpoint not found: {api_url}")
                    continue
                else:
                    logger.error(f"API error at {api_url}: {response.status_code} - {response.text}")
                    continue

        except httpx.TimeoutException:
            logger.error(f"Timeout with endpoint: {api_url}")
            continue
        except Exception as e:
            logger.error(f"Failed with endpoint {api_url}: {e}", exc_info=True)
            continue
    
    logger.error("All endpoint attempts failed for video generation.")
    return None

# ================== BOT EVENT HANDLERS ==================

# --- Command Handlers ---

async def is_admin(event):
    """Check if the user is an admin in the chat."""
    try:
        user = await event.get_sender()
        if not user:
            return False
        
        if event.is_private:
            return True

        perms = await event.client.get_permissions(event.chat_id, user.id)
        return perms.is_admin or perms.is_creator
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

@client.on(events.NewMessage(pattern=r'^/boton'))
async def boton_handler(event):
    if not await is_admin(event):
        return await send_deletable_message(event.chat_id, "You are not authorized to use this command.")

    config = load_config()
    chat_id_str = str(event.chat_id)
    if chat_id_str not in config['ai_enabled_config']:
        config['ai_enabled_config'][chat_id_str] = True
        save_config(config)
        await send_deletable_message(event.chat_id, "🤖 AI is now ON.")
    elif not config['ai_enabled_config'][chat_id_str]:
        config['ai_enabled_config'][chat_id_str] = True
        save_config(config)
        await send_deletable_message(event.chat_id, "🤖 AI is now ON.")
    else:
        await send_deletable_message(event.chat_id, "🤖 AI is already ON.")

@client.on(events.NewMessage(pattern=r'^/botoff'))
async def botoff_handler(event):
    if not await is_admin(event):
        return await send_deletable_message(event.chat_id, "You are not authorized to use this command.")

    config = load_config()
    chat_id_str = str(event.chat_id)
    if chat_id_str in config['ai_enabled_config'] and config['ai_enabled_config'][chat_id_str]:
        config['ai_enabled_config'][chat_id_str] = False
        save_config(config)
        await send_deletable_message(event.chat_id, "🤖 AI is now OFF.")
    else:
        await send_deletable_message(event.chat_id, "🤖 AI is already OFF.")

@client.on(events.NewMessage(pattern=r'^/ai'))
async def ai_handler(event):
    # AI handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/trivia'))
async def trivia_handler(event):
    # Trivia handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/help'))
async def help_handler(event):
    help_text = """
    **Astrophile Bot Commands**

    • `/ai [prompt]` - Ask the AI anything.
    • `/trivia` - Start a trivia game.
    • `/help` - Show this help message.
    • `/sticker [prompt]` - Generate a sticker.
    • `/image [prompt]` - Generate an image.
    • `/vision [reply to image]` - Analyze an image.
    • `/latex [formula]` - Render a LaTeX formula.

    **Admin Commands**
    • `/boton` - Enable AI.
    • `/botoff` - Disable AI.
    • `/ban [reply]` - Ban a user.
    • `/mute [reply]` - Mute a user.
    • `/delete [reply]` - Delete a message.
    • `/lock` - Lock chat permissions.
    • `/unlock` - Unlock chat permissions.

    *Note: For voice calls, use /joincall with Ray userbot*
    """
    await event.reply(help_text)

@client.on(events.NewMessage(pattern=r'^/sticker'))
async def sticker_handler(event):
    # Sticker handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/image'))
async def image_handler(event):
    # Image handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/vision'))
async def vision_handler(event):
    # Vision handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/latex'))
async def latex_handler(event):
    # LaTeX handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/ban'))
async def ban_handler(event):
    if not await is_admin(event): return
    # Ban handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/mute'))
async def mute_handler(event):
    if not await is_admin(event): return
    # Mute handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/delete'))
async def delete_handler(event):
    if not await is_admin(event): return
    # Delete handler logic here
    pass

@client.on(events.NewMessage(pattern=r'^/kick'))
async def kick_handler(event):
    if not await is_admin(event): return
    # Kick handler logic here
    pass
    
@client.on(events.NewMessage(pattern=r'^/lock'))
async def lock_handler(event):
    if not await is_admin(event): return
    # Lock handler logic here
    pass

# --- Main Execution ---
async def start_bot():
    """Initializes and starts the bot."""
    global global_context
    
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()

    global_context = BotContext(client)
    await global_context.initialize()

    logger.info("=" * 50)
    logger.info("🤖 ASTROPHILE BOT MODE")
    logger.info("=" * 50)
    logger.info(f"Bot: @{me.username}")
    logger.info(f"ID: {me.id}")
    logger.info("Mode: Telegram Bot (BOT_TOKEN)")
    logger.info("Call features: Use Ray userbot")
    logger.info("=" * 50)
    
    logger.info("🤖 Astrophile bot is running...")
    return me

if __name__ == '__main__':
    logger.info("🤖 Starting Astrophile bot in BOT mode...")
    with client:
        client.loop.run_until_complete(start_bot())
        client.run_until_disconnected()
