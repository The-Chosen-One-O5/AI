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

# --- TTS/STT Imports ---
import edge_tts
from faster_whisper import WhisperModel
import soundfile as sf
import numpy as np
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# --- pytgcalls Imports ---
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from telethon import TelegramClient

# --- Telethon Imports (Replaces python-telegram-bot) ---
from telethon import TelegramClient, events, types, functions, errors
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, ChannelParticipantsAdmins
from telethon.tl.functions.messages import SendReactionRequest

# --- Userbot Bootstrap ---
from userbot import create_userbot_from_env, UserbotClient

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

# --- Telethon Userbot Configuration ---
API_ID = os.environ.get('API_ID')  # Telegram API ID for Telethon userbot
API_HASH = os.environ.get('API_HASH')  # Telegram API Hash for Telethon userbot
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')  # Phone number for userbot authentication
SESSION_PATH = os.environ.get('SESSION_PATH', 'userbot_session')  # Session file path

# --- TTS/STT Configuration ---
WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')  # tiny, base, small, medium, large
EDGE_TTS_VOICE = os.environ.get('EDGE_TTS_VOICE', 'en-US-AriaNeural')  # Default voice
EDGE_TTS_RATE = os.environ.get('EDGE_TTS_RATE', '+0%')  # Speech rate adjustment
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', 'ffmpeg')  # FFmpeg binary path

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
if not PHONE_NUMBER:
    print("FATAL ERROR: PHONE_NUMBER environment variable not set!")
    print("Use international format like +1234567890")
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
active_calls = {}  # {chat_id: {"state": "active/idle", "participants": [], "transcript": deque(), "last_response_time": datetime, "error_count": 0, "call_handler": PyTgCalls}}
audio_buffers = {}  # {chat_id: deque of audio chunks}
tts_queues = {}  # {chat_id: asyncio.Queue for TTS chunks}

# --- Global TTS/STT Services ---
whisper_model: Optional[WhisperModel] = None
telethon_client: Optional[TelegramClient] = None
pytgcalls_instances = {}  # {chat_id: PyTgCalls instance}
userbot_instance: Optional[UserbotClient] = None  # Global userbot client manager

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
            context_obj = type('Context', (), {'job': job_data, 'bot': global_global_context.bot})()
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
                context_obj = type('Context', (), {'job': job_data, 'bot': global_global_context.bot})()
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
            "audio_mode_config": {}, "proactive_call_config": {},
            "call_quiet_hours": {},  # {chat_id: {"start": "22:00", "end": "08:00"}}
            "tts_config": {},  # {chat_id: {"enabled": bool, "voice": str, "rate": str, "language": str}}
            "stt_config": {},   # {chat_id: {"enabled": bool, "language": str, "sensitivity": float}}
            "session_path": "userbot_session",  # Telethon session file path
            "use_string_session": False  # Use string session for cloud deployment
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
        # Replicate's run is blocking, use async_run for non-blocking if replicate library supports it well
        # Note: Check replicate library documentation for best async practices. Using blocking run in thread for now.
        output = await asyncio.to_thread(
            replicate.run,
            "minimax/speech-02-hd:408e2f3d6f1f0a149b5c777d8a0f5a7707e99741a4a15995f532b13c77e779a1", # Use full model identifier
            input=input_params
        )

        if not output:
            logger.error("Replicate API did not return output.")
            return None
        output_url = output # Assuming output is the URL directly

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
    
    # Try different possible endpoint formats
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

# --- TTS/STT Services ---

async def initialize_whisper_model():
    """Initialize faster-whisper model for transcription."""
    global whisper_model
    if whisper_model is None:
        try:
            logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
            whisper_model = await asyncio.to_thread(
                WhisperModel,
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8"
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
            whisper_model = None
    return whisper_model

async def convert_audio_format(input_path: str, output_path: str, format: str = "wav", sample_rate: int = 48000, channels: int = 2) -> bool:
    """Convert audio using FFmpeg with async subprocess."""
    try:
        cmd = [
            FFMPEG_PATH,
            "-i", input_path,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-f", format,
            "-y",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {stderr.decode()}")
            return False
        
        logger.debug(f"Audio converted successfully: {input_path} -> {output_path}")
        return True
    except Exception as e:
        logger.error(f"Audio conversion error: {e}", exc_info=True)
        return False

async def generate_tts_audio(text: str, voice: str = None, rate: str = None) -> Optional[bytes]:
    """Generate TTS audio using Edge-TTS."""
    if not text.strip():
        return None
    
    voice = voice or EDGE_TTS_VOICE
    rate = rate or EDGE_TTS_RATE
    
    # Remove markdown for cleaner TTS
    cleaned_text = re.sub(r'[*_`]', '', text)
    
    # Split long text into chunks (Edge-TTS has limits)
    max_length = 500
    if len(cleaned_text) > max_length:
        cleaned_text = cleaned_text[:max_length]
    
    try:
        logger.info(f"Generating TTS with Edge-TTS (voice: {voice}, rate: {rate})")
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_mp3:
            temp_mp3_path = temp_mp3.name
        
        try:
            # Generate audio with Edge-TTS
            communicate = edge_tts.Communicate(cleaned_text, voice, rate=rate)
            await communicate.save(temp_mp3_path)
            
            # Convert to PCM WAV for pytgcalls
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            success = await convert_audio_format(
                temp_mp3_path, 
                temp_wav_path,
                format="s16le",
                sample_rate=48000,
                channels=2
            )
            
            if not success:
                logger.error("Failed to convert TTS audio to PCM")
                return None
            
            # Read the converted audio
            with open(temp_wav_path, "rb") as f:
                audio_data = f.read()
            
            logger.info(f"TTS audio generated successfully ({len(audio_data)} bytes)")
            return audio_data
            
        finally:
            # Cleanup temp files
            for path in [temp_mp3_path, temp_wav_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        return None

async def transcribe_with_whisper(audio_bytes: bytes, language: str = "en") -> Optional[Tuple[str, dict]]:
    """Transcribe audio using faster-whisper with timestamps."""
    model = await initialize_whisper_model()
    if not model:
        logger.error("Whisper model not available")
        return None
    
    try:
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name
        
        try:
            # Convert to WAV for Whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            success = await convert_audio_format(
                temp_audio_path,
                temp_wav_path,
                format="wav",
                sample_rate=16000,
                channels=1
            )
            
            if not success:
                logger.error("Failed to convert audio for transcription")
                return None
            
            # Transcribe with Whisper
            logger.info("Transcribing audio with faster-whisper...")
            start_time = asyncio.get_event_loop().time()
            
            segments, info = await asyncio.to_thread(
                model.transcribe,
                temp_wav_path,
                language=language,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect segments with timestamps
            transcript_parts = []
            segment_data = []
            
            for segment in segments:
                transcript_parts.append(segment.text)
                segment_data.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                })
            
            full_transcript = " ".join(transcript_parts).strip()
            
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"Transcription completed in {elapsed:.2f}s: {full_transcript[:100]}...")
            
            return full_transcript, {
                "segments": segment_data,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration
            }
        
        finally:
            # Cleanup temp files
            for path in [temp_audio_path, temp_wav_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}", exc_info=True)
        return None

async def initialize_telethon_client():
    """Initialize the global Telethon client for pytgcalls."""
    global telethon_client
    
    if telethon_client is not None:
        return telethon_client
    
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH required for Telethon/pytgcalls")
        return None
    
    try:
        logger.info("Initializing Telethon client...")
        telethon_client = TelegramClient(
            'bot_session',
            int(API_ID),
            API_HASH
        )
        await telethon_client.start(bot_token=BOT_TOKEN)
        logger.info("✅ Telethon client started successfully")
        return telethon_client
    
    except Exception as e:
        logger.error(f"Failed to initialize Telethon client: {e}", exc_info=True)
        telethon_client = None
        return None

async def shutdown_telethon_client():
    """Gracefully shutdown the Telethon client."""
    global telethon_client, pytgcalls_instances
    
    try:
        # Disconnect all pytgcalls instances first
        for chat_id, pytg_client in list(pytgcalls_instances.items()):
            try:
                await leave_voice_chat(int(chat_id))
            except Exception as e:
                logger.error(f"Error leaving call in chat {chat_id}: {e}")
        
        pytgcalls_instances.clear()
        
        # Disconnect Telethon client
        if telethon_client:
            await telethon_client.disconnect()
            telethon_client = None
            logger.info("✅ Telethon client disconnected")
    
    except Exception as e:
        logger.error(f"Error during Telethon shutdown: {e}", exc_info=True)

async def initialize_pytgcalls(chat_id: int):
    """Initialize pytgcalls for a specific chat."""
    global telethon_client, pytgcalls_instances
    
    chat_id_str = str(chat_id)
    
    # Return existing instance if available
    if chat_id_str in pytgcalls_instances:
        pytg_client = pytgcalls_instances[chat_id_str]
        # Check if instance is still active
        try:
            if pytg_client:
                return pytg_client
        except:
            pass
    
    try:
        # Ensure Telethon client is initialized
        client = await initialize_telethon_client()
        if not client:
            logger.error("Cannot initialize pytgcalls: Telethon client failed")
            return None
        
        # Create pytgcalls instance
        logger.info(f"Creating pytgcalls instance for chat {chat_id}")
        pytg_client = PyTgCalls(client)
        await pytg_client.start()
        
        pytgcalls_instances[chat_id_str] = pytg_client
        logger.info(f"✅ pytgcalls instance created for chat {chat_id}")
        
        return pytg_client
    
    except Exception as e:
        logger.error(f"Failed to initialize pytgcalls for chat {chat_id}: {e}", exc_info=True)
        return None

async def join_voice_chat(chat_id: int, auto_join: bool = False) -> bool:
    """Join a voice chat in the specified chat."""
    global active_calls
    
    chat_id_str = str(chat_id)
    
    try:
        # Initialize pytgcalls for this chat
        pytg_client = await initialize_pytgcalls(chat_id)
        if not pytg_client:
            logger.error(f"Cannot join call: pytgcalls initialization failed for chat {chat_id}")
            return False
        
        # Check if already in call
        if chat_id_str in active_calls and active_calls[chat_id_str].get("state") == "joined":
            logger.info(f"Already in voice chat for chat {chat_id}")
            return True
        
        # Initialize call state
        if chat_id_str not in active_calls:
            active_calls[chat_id_str] = {
                "state": "idle",
                "participants": [],
                "transcript": deque(maxlen=20),
                "last_response_time": None,
                "error_count": 0,
                "join_time": None,
                "auto_joined": auto_join
            }
        
        # Join the call with a silent audio stream (ready to play audio)
        logger.info(f"Joining voice chat in chat {chat_id}...")
        
        # Create a silent audio file for initial connection
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as temp_file:
            # Generate 1 second of silence (48kHz stereo 16-bit PCM)
            silence = b'\x00' * (48000 * 2 * 2)  # sample_rate * channels * bytes_per_sample
            temp_file.write(silence)
            silent_audio_path = temp_file.name
        
        try:
            await pytg_client.join_group_call(
                chat_id,
                AudioPiped(silent_audio_path),
                stream_type=StreamType().pulse_stream
            )
            
            # Update call state
            active_calls[chat_id_str]["state"] = "joined"
            active_calls[chat_id_str]["join_time"] = datetime.now()
            active_calls[chat_id_str]["error_count"] = 0
            
            logger.info(f"✅ Successfully joined voice chat in chat {chat_id}")
            
            # Initialize audio buffer and TTS queue
            if chat_id_str not in audio_buffers:
                audio_buffers[chat_id_str] = deque(maxlen=100)
            if chat_id_str not in tts_queues:
                tts_queues[chat_id_str] = asyncio.Queue()
            
            return True
        
        finally:
            # Cleanup temporary file after a delay
            await asyncio.sleep(2)
            if os.path.exists(silent_audio_path):
                os.unlink(silent_audio_path)
    
    except Exception as e:
        logger.error(f"Failed to join voice chat in chat {chat_id}: {e}", exc_info=True)
        
        # Update error count
        if chat_id_str in active_calls:
            active_calls[chat_id_str]["error_count"] = active_calls[chat_id_str].get("error_count", 0) + 1
        
        return False

async def leave_voice_chat(chat_id: int) -> bool:
    """Leave a voice chat in the specified chat."""
    global active_calls, pytgcalls_instances
    
    chat_id_str = str(chat_id)
    
    try:
        pytg_client = pytgcalls_instances.get(chat_id_str)
        
        if not pytg_client:
            logger.warning(f"No pytgcalls instance found for chat {chat_id}")
            # Still clean up state
            if chat_id_str in active_calls:
                active_calls[chat_id_str]["state"] = "left"
            return True
        
        logger.info(f"Leaving voice chat in chat {chat_id}...")
        
        # Leave the group call
        await pytg_client.leave_group_call(chat_id)
        
        # Update call state
        if chat_id_str in active_calls:
            active_calls[chat_id_str]["state"] = "left"
            active_calls[chat_id_str]["transcript"].clear()
        
        # Clean up buffers
        if chat_id_str in audio_buffers:
            audio_buffers[chat_id_str].clear()
        if chat_id_str in tts_queues:
            # Clear the queue
            while not tts_queues[chat_id_str].empty():
                try:
                    tts_queues[chat_id_str].get_nowait()
                except:
                    break
        
        logger.info(f"✅ Successfully left voice chat in chat {chat_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error leaving voice chat in chat {chat_id}: {e}", exc_info=True)
        # Still try to clean up state
        if chat_id_str in active_calls:
            active_calls[chat_id_str]["state"] = "left"
        return False

async def get_call_state(chat_id: int) -> dict:
    """Get the current call state for a chat."""
    chat_id_str = str(chat_id)
    return active_calls.get(chat_id_str, {
        "state": "idle",
        "participants": [],
        "transcript": deque(),
        "last_response_time": None,
        "error_count": 0
    })

async def is_in_call(chat_id: int) -> bool:
    """Check if the bot is currently in a voice chat."""
    chat_id_str = str(chat_id)
    call_state = active_calls.get(chat_id_str, {})
    return call_state.get("state") == "joined"

async def stream_tts_to_call(chat_id: int, text: str, voice: str = None, rate: str = None):
    """Stream TTS audio to a voice call using pytgcalls."""
    try:
        # Check if in call first
        if not await is_in_call(chat_id):
            logger.warning(f"Cannot stream TTS: not in voice chat for chat {chat_id}")
            return False
        
        pytg_client = await initialize_pytgcalls(chat_id)
        if not pytg_client:
            logger.error(f"Cannot stream TTS: pytgcalls not initialized for chat {chat_id}")
            return False
        
        # Generate TTS audio
        audio_data = await generate_tts_audio(text, voice, rate)
        if not audio_data:
            logger.error("Failed to generate TTS audio")
            return False
        
        # Convert audio to proper format for streaming (PCM 48kHz stereo)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Convert to raw PCM for streaming
            success = await convert_audio_format(
                input_path, 
                output_path, 
                format="s16le",  # 16-bit PCM
                sample_rate=48000,
                channels=2
            )
            
            if not success:
                logger.error("Failed to convert audio for streaming")
                return False
            
            # Change stream to the new audio
            await pytg_client.change_stream(
                chat_id,
                AudioPiped(output_path)
            )
            
            logger.info(f"✅ TTS audio streamed to call in chat {chat_id}")
            return True
        
        finally:
            # Cleanup temporary files after streaming
            await asyncio.sleep(3)  # Give time for streaming to complete
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"Failed to stream TTS to call: {e}", exc_info=True)
        return False

async def play_audio_to_call(chat_id: int, audio_path: str) -> bool:
    """Play an audio file to a voice call."""
    try:
        if not await is_in_call(chat_id):
            logger.warning(f"Cannot play audio: not in voice chat for chat {chat_id}")
            return False
        
        pytg_client = await initialize_pytgcalls(chat_id)
        if not pytg_client:
            logger.error(f"Cannot play audio: pytgcalls not initialized for chat {chat_id}")
            return False
        
        # Convert audio to proper format
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as temp_file:
            output_path = temp_file.name
        
        try:
            success = await convert_audio_format(
                audio_path,
                output_path,
                format="s16le",
                sample_rate=48000,
                channels=2
            )
            
            if not success:
                return False
            
            # Change stream to play the audio
            await pytg_client.change_stream(
                chat_id,
                AudioPiped(output_path)
            )
            
            logger.info(f"✅ Audio file played to call in chat {chat_id}")
            return True
        
        finally:
            # Cleanup
            await asyncio.sleep(3)
            if os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Failed to play audio to call: {e}", exc_info=True)
        return False

async def capture_call_audio(chat_id: int, duration: int = 5) -> Optional[bytes]:
    """Capture audio frames from a voice call for STT processing."""
    try:
        chat_id_str = str(chat_id)
        
        if not await is_in_call(chat_id):
            logger.warning(f"Cannot capture audio: not in voice chat for chat {chat_id}")
            return None
        
        # Get audio buffer for this chat
        if chat_id_str not in audio_buffers:
            audio_buffers[chat_id_str] = deque(maxlen=100)
        
        audio_buffer = audio_buffers[chat_id_str]
        
        # Wait to collect audio frames
        await asyncio.sleep(duration)
        
        # Combine captured frames
        if len(audio_buffer) == 0:
            logger.debug(f"No audio captured from call in chat {chat_id}")
            return None
        
        # Convert frames to bytes
        audio_data = b''.join(audio_buffer)
        audio_buffer.clear()
        
        return audio_data
    
    except Exception as e:
        logger.error(f"Failed to capture call audio: {e}", exc_info=True)
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

async def send_final_response(event, response_text: str | None, thinking_message, prompt_title: str):
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
            await global_context.bot.edit_message_text(error_message, chat_id=event.chat_id, message_id=thinking_message.message_id)
        except errors.RPCError: pass # Ignore if original message deleted
        return

    config = load_config()
    chat_id = str(event.chat_id)
    is_audio_mode = config.get("audio_mode_config", {}).get(chat_id, False)

    if is_audio_mode:
        try:
            await global_context.bot.edit_message_text("🎤 Generating audio...", chat_id=event.chat_id, message_id=thinking_message.message_id)
        except errors.RPCError: pass # Ignore if original message deleted

        audio_bytes = await generate_audio_from_text(response_text)
        if audio_bytes:
            try:
                await global_context.bot.send_voice(chat_id=event.chat_id, voice=audio_bytes)
                # Delete thinking message after sending audio
                try: await thinking_message.delete()
                except errors.RPCError: pass
            except Exception as e:
                 logger.error(f"Failed to send voice message: {e}")
                 # Fallback to text if sending voice fails
                 try:
                     await global_context.bot.edit_message_text("Failed to send audio, sending text.", chat_id=event.chat_id, message_id=thinking_message.message_id)
                 except errors.RPCError: pass
                 await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)
        else:
            try:
                await global_context.bot.edit_message_text("Audio generation failed, sending text.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            except errors.RPCError: pass
            await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)
    else:
        # Send as text or telegraph page
        await send_or_telegraph_fallback(update, context, response_text, thinking_message, prompt_title)

async def send_or_telegraph_fallback(event, response_text: str, thinking_message, prompt_title: str):
    try:
        if len(response_text) > 4000:
            await global_context.bot.edit_message_text("Response too long, creating Telegraph page...", chat_id=event.chat_id, message_id=thinking_message.message_id)
            # Run blocking telegraph creation in a separate thread
            url = await asyncio.to_thread(create_telegraph_page, prompt_title, response_text, load_config())
            final_message = f"The response was too long. I've posted it here:\n{url}" if url else f"Response too long, and failed to post to Telegraph. Truncated:\n\n{response_text[:3800]}..."
            await global_context.bot.edit_message_text(final_message, chat_id=event.chat_id, message_id=thinking_message.message_id)
        else:
            # Try sending with Markdown, fall back to plain text if it fails
            try:
                await global_context.bot.edit_message_text(response_text, chat_id=event.chat_id, message_id=thinking_message.message_id, parse_mode='Markdown')
            except errors.RPCError:
                logger.warning("Markdown parsing failed, sending as plain text.")
                await global_context.bot.edit_message_text(response_text, chat_id=event.chat_id, message_id=thinking_message.message_id)
    except errors.RPCError as e:
         # Handle cases where the thinking_message might have been deleted already
         if "Message to edit not found" in str(e):
             logger.warning("Thinking message was likely deleted before final response.")
             # Optionally send response as a new message if edit fails
             # await event.reply(response_text[:4000]) # Example
         else:
             logger.error(f"Failed to edit message: {e}")
    except Exception as e:
         logger.error(f"Unexpected error in send_or_telegraph_fallback: {e}")


async def is_user_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin using Telethon"""
    if chat_id > 0: return False  # No admins in private chats
    try:
        chat_admins = await global_context.bot.get_chat_administrators(chat_id)
        return any(admin.id == user_id for admin in chat_admins)
    except errors.RPCError:
        logger.warning(f"Could not get admins for chat {chat_id}. Assuming user {user_id} is not admin.")
        return False # No admins in private chats
    try:
        chat_admins = await global_context.bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in chat_admins)
    except errors.RPCError:
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

    except errors.RPCErrorError as e:
        logger.error(f"Groq API errors.RPCErrorError (possibly deprecated model): {e}")
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
                logger.error(f"ChatAnywhere API errors.RPCError (possibly deprecated model): {response.text}")
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

async def generate_sticker_image(prompt: str) -> bytes | None:
    """Generates an image for sticker using Samurai API with Qwen models."""
    if not SAMURAI_API_KEY:
        logger.error("Samurai API key not configured. Cannot generate sticker image.")
        return None

    logger.info(f"Generating sticker image with Samurai API for prompt: {prompt}")
    
    # Try different endpoint formats
    api_urls = [
        "https://samuraiapi.in/v1/images/generations",
        "https://samuraiapi.in/v1/image/generations",
        "https://api.samuraiapi.in/v1/images/generations"
    ]
    
    models = ["free/qwen-qwen-image", "free/qwen-qwen-image/p-2"]
    
    for api_url in api_urls:
        for model in models:
            try:
                logger.info(f"Trying endpoint: {api_url} with model: {model}")
                
                headers = {
                    "Authorization": f"Bearer {SAMURAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024"
                }

                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    response = await client.post(api_url, headers=headers, json=payload)
                    
                    logger.info(f"Response status: {response.status_code}")
                    logger.info(f"Response body preview: {response.text[:500]}")

                    if response.status_code == 200:
                        result_data = response.json().get("data")
                        if result_data and isinstance(result_data, list) and len(result_data) > 0:
                            image_url = result_data[0].get("url")
                            if image_url:
                                logger.info(f"Downloading image from: {image_url}")
                                image_response = await client.get(image_url, timeout=120.0)
                                image_response.raise_for_status()
                                logger.info(f"Image downloaded successfully using {model} at {api_url}.")
                                return image_response.content
                        
                        logger.warning(f"Unexpected response structure from {api_url}")
                        continue
                        
                    elif response.status_code == 404:
                        logger.warning(f"Endpoint not found: {api_url}")
                        break  # Try next URL
                    else:
                        logger.warning(f"API error: {response.status_code} - {response.text}")
                        continue

            except httpx.TimeoutException:
                logger.warning(f"Timeout with {api_url} and model {model}")
                continue
            except Exception as e:
                logger.warning(f"Failed with {api_url} and model {model}: {e}")
                continue
    
    logger.error("All endpoint and model attempts failed for sticker generation.")
    return None

async def convert_to_sticker(image_bytes: bytes) -> bytes | None:
    """Converts an image to sticker format (512x512 WebP)."""
    try:
        from PIL import Image
        import io
        
        # Open the image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Resize to 512x512 (Telegram sticker requirement)
        img = img.resize((512, 512), Image.Resampling.LANCZOS)
        
        # Save as WebP
        output = io.BytesIO()
        img.save(output, format='WEBP')
        output.seek(0)
        
        logger.info("Image converted to sticker format successfully.")
        return output.read()
        
    except Exception as e:
        logger.error(f"Failed to convert image to sticker format: {e}", exc_info=True)
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

# --- Proactive Call Management ---

async def transcribe_audio(audio_bytes: bytes, language: str = "en") -> str | None:
    """Transcribe audio using faster-whisper (local) with fallback to Groq."""
    # Try local faster-whisper first
    result = await transcribe_with_whisper(audio_bytes, language)
    if result:
        transcript, metadata = result
        return transcript
    
    # Fallback to Groq's Whisper API if local fails
    if not GROQ_API_KEY:
        logger.warning("Groq API key not set and local whisper failed, cannot transcribe audio.")
        return None
    
    try:
        logger.info("Falling back to Groq Whisper API...")
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name
        
        try:
            client = AsyncGroq(api_key=GROQ_API_KEY)
            
            with open(temp_audio_path, "rb") as audio_file:
                transcription = await client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text",
                    language=language
                )
            
            if transcription:
                logger.info(f"Transcribed audio with Groq: {transcription[:100]}...")
                return transcription.strip()
            else:
                logger.warning("Groq Whisper returned empty transcription.")
                return None
        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
    
    except Exception as e:
        logger.error(f"Audio transcription failed: {e}", exc_info=True)
        return None

def is_in_quiet_hours(chat_id: str) -> bool:
    """Check if current time is within configured quiet hours for a chat."""
    config = load_config()
    quiet_hours = config.get("call_quiet_hours", {}).get(chat_id)
    
    if not quiet_hours:
        return False
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist).time()
        
        start_str = quiet_hours.get("start", "22:00")
        end_str = quiet_hours.get("end", "08:00")
        
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        
        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    
    except Exception as e:
        logger.error(f"Error checking quiet hours: {e}")
        return False

def should_auto_join_call(chat_id: str, participant_count: int = 0) -> bool:
    """Determine if bot should auto-join a call based on configuration."""
    config = load_config()
    call_config = config.get("proactive_call_config", {}).get(chat_id, {})
    
    # Check if proactive calls are enabled
    if not call_config.get("enabled", False):
        return False
    
    # Check quiet hours
    if is_in_quiet_hours(chat_id):
        logger.info(f"Skipping auto-join for chat {chat_id}: in quiet hours")
        return False
    
    # Check minimum participant requirement
    min_participants = call_config.get("min_participants", 2)
    if participant_count < min_participants:
        logger.info(f"Skipping auto-join for chat {chat_id}: only {participant_count} participants (need {min_participants})")
        return False
    
    return True

async def generate_call_response(chat_id: str) -> str | None:
    """Generate contextual AI response based on call transcript and chat history."""
    call_state = active_calls.get(chat_id)
    if not call_state:
        return None
    
    # Check rate limiting
    last_response = call_state.get("last_response_time")
    if last_response:
        time_since_last = (datetime.now() - last_response).total_seconds()
        cooldown = 30  # Minimum 30 seconds between responses
        if time_since_last < cooldown:
            logger.info(f"Skipping response for chat {chat_id}: cooldown active ({time_since_last:.1f}s < {cooldown}s)")
            return None
    
    # Merge transcript with recent chat history
    transcript = "\n".join(call_state.get("transcript", deque()))
    chat_history = "\n".join(chat_histories.get(int(chat_id), deque()))
    
    if not transcript and not chat_history:
        return None
    
    combined_context = f"Recent chat:\n{chat_history}\n\nCall transcript:\n{transcript}"
    
    # Generate response
    prompt = (
        "You are AI618, participating in a group voice call. Based on the context below, "
        "generate ONE brief, natural response (under 20 words). Be conversational and contextual. "
        "If the conversation is unclear or no response is needed, say 'SKIP'.\n\n"
        f"{combined_context}\n\n--- Your Response ---"
    )
    
    messages = [{"role": "system", "content": prompt}]
    response = await get_typegpt_response(messages)
    
    if response and "SKIP" not in response.upper():
        # Update last response time
        call_state["last_response_time"] = datetime.now()
        call_state["error_count"] = 0  # Reset error count on success
        return response
    
    return None

async def handle_call_audio(event):
    """Handle voice messages in active calls for transcription and response with TTS/STT."""
    if not update.message or not event.voice:
        return
    
    chat_id = str(event.chat_id)
    chat_id_int = int(chat_id)
    
    # Check if this chat has proactive calls or STT enabled
    config = load_config()
    proactive_enabled = config.get("proactive_call_config", {}).get(chat_id, {}).get("enabled", False)
    stt_config = config.get("stt_config", {}).get(chat_id, {})
    stt_enabled = stt_config.get("enabled", False)
    
    if not (proactive_enabled or stt_enabled):
        return
    
    # Initialize call state if needed
    if chat_id not in active_calls:
        active_calls[chat_id] = {
            "state": "active",
            "participants": [],
            "transcript": deque(maxlen=20),
            "last_response_time": None,
            "error_count": 0
        }
    
    call_state = active_calls[chat_id]
    
    try:
        # Download and transcribe audio
        voice_file = await event.voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
        
        # Use configured STT language or default to English
        stt_language = stt_config.get("language", "en")
        transcription = await transcribe_audio(bytes(audio_bytes), stt_language)
        
        if transcription:
            # Add to transcript with timestamp
            user_name = event.sender.first_name or "User"
            timestamp = datetime.now().strftime("%H:%M:%S")
            call_state["transcript"].append(f"[{timestamp}] {user_name}: {transcription}")
            logger.info(f"[{timestamp}] Transcribed - {user_name}: {transcription[:50]}...")
            
            # Decide if bot should respond
            should_respond = random.random() < 0.3  # 30% chance to respond
            
            if should_respond:
                response = await generate_call_response(chat_id, context)
                
                if response:
                    # Check TTS configuration
                    tts_config = config.get("tts_config", {}).get(chat_id, {})
                    tts_enabled = tts_config.get("enabled", False)
                    is_audio_mode = config.get("audio_mode_config", {}).get(chat_id, False)
                    
                    if tts_enabled or is_audio_mode:
                        # Try to stream TTS to call first
                        voice = tts_config.get("voice", EDGE_TTS_VOICE)
                        rate = tts_config.get("rate", EDGE_TTS_RATE)
                        
                        streamed = await stream_tts_to_call(chat_id_int, response, voice, rate)
                        
                        if not streamed:
                            # Fallback: generate TTS audio and send as voice message
                            audio_data = await generate_tts_audio(response, voice, rate)
                            if audio_data:
                                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                                    temp_file.write(audio_data)
                                    temp_path = temp_file.name
                                
                                try:
                                    await global_context.bot.send_voice(chat_id=chat_id_int, voice=open(temp_path, 'rb'))
                                finally:
                                    if os.path.exists(temp_path):
                                        os.unlink(temp_path)
                            else:
                                # Ultimate fallback to text
                                await global_context.bot.send_message(chat_id=chat_id_int, text=response)
                    else:
                        # Send text response
                        await global_context.bot.send_message(chat_id=chat_id_int, text=response)
        else:
            # Track transcription failures
            call_state["error_count"] = call_state.get("error_count", 0) + 1
            
            # If too many errors, warn and potentially disable
            if call_state["error_count"] >= 5:
                logger.warning(f"Too many transcription errors in chat {chat_id}, may need intervention")
                await global_context.bot.send_message(
                    chat_id=chat_id_int,
                    text="⚠️ I'm having trouble hearing the call. Check /sttconfig or /callleave."
                )
                call_state["error_count"] = 0  # Reset after warning
    
    except Exception as e:
        logger.error(f"Error handling call audio in chat {chat_id}: {e}", exc_info=True)
        call_state["error_count"] = call_state.get("error_count", 0) + 1

# --- Trivia System ---
async def poll_answer_handler(event):
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

async def start_trivia(event, topic: str, question_count: int):
    chat_id = str(event.chat_id)
    if trivia_sessions.get(chat_id, {}).get("state") in ["registering", "asking"]:
        await event.reply("A game is already in progress!")
        return

    intro_text = (f"Alright, trivia time! 🔥 **{question_count}** rounds on **{topic}**.\n\n"
                  "Who's playing? Reply to this message with `me` to join.\n"
                  "When ready, someone reply `all in` to start!")
    intro_message = await event.reply(intro_text, parse_mode='Markdown')
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
        poll_message = await global_context.bot.send_poll(
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
        global_context.job_queue.run_once(
             process_poll_end_callback,
             62, # open_period + buffer
             data={'chat_id': chat_id, 'expected_poll_id': poll_message.poll.id},
             name=f"trivia_poll_end_{chat_id}_{poll_message.poll.id}"
         )

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
        await global_context.bot.send_message(int(chat_id), leaderboard, parse_mode='Markdown')
    except Exception as e:
         logger.error(f"Failed to send final leaderboard: {e}")
    if chat_id in trivia_sessions:
        trivia_sessions[chat_id]["state"] = "finished" # Use 'finished' state # Mark game as over

# --- Master Handlers ---

async def smart_ai_handler(event) -> None:
    # Ensure update and message exist
    if not update.message or not event.text:
        return

    prompt = " ".join(event.text.split()[1:])
    if not prompt:
        await event.reply("Please provide a prompt after /ai.")
        return

    chat_id_str = str(event.chat_id)
    config = load_config()
    # Check if AI features are enabled for this chat
    if not config.get("ai_enabled_config", {}).get(chat_id_str, False):
        await event.reply("AI features are currently disabled in this group. Ask an admin to use `/boton`.")
        return

    thinking_message = await event.reply("Processing...")

    try:
        # Trivia control commands (Admin only)
        trivia_match = re.search(r'start trivia(?: on (.+?))?(?: (\d+)Q)?$', prompt, re.IGNORECASE)
        if trivia_match:
            if not await is_user_admin(event.chat_id, event.sender.id):
                 await global_context.bot.edit_message_text("Only admins can start trivia games.", chat_id=event.chat_id, message_id=thinking_message.message_id)
                 return
            topic = (trivia_match.group(1) or "general knowledge").strip()
            q_count = int(trivia_match.group(2) or 5)
            await thinking_message.delete() # Delete "Processing..." before starting game
            await start_trivia(update, context, topic, q_count)
            return
            
        if "stop trivia" in prompt.lower():
            if not await is_user_admin(event.chat_id, event.sender.id):
                 await global_context.bot.edit_message_text("Only admins can stop trivia games.", chat_id=event.chat_id, message_id=thinking_message.message_id)
                 return
            if chat_id_str in trivia_sessions and trivia_sessions[chat_id_str].get("state") != "inactive":
                await thinking_message.delete()
                await end_trivia(context, chat_id_str, "The game was stopped early by an admin.")
            else:
                await global_context.bot.edit_message_text("No trivia game is currently running.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            return

        # Gossip Memory commands
        if event.reply_to_msg_id and await event.get_reply_message() and ("remember this" in prompt.lower()):
            replied = event.reply_to_msg_id and await event.get_reply_message()
            if replied.text:
                gossip = load_gossip()
                gossip.setdefault(chat_id_str, []).append({
                    "author": replied.from_user.first_name or "User",
                    "author_username": replied.from_user.username or "",
                    "text": replied.text,
                    "saved_by": event.sender.first_name or "User",
                    "timestamp": datetime.now().isoformat()
                })
                save_gossip(gossip)
                await global_context.bot.edit_message_text("Alright, I'll remember that one.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            else:
                await global_context.bot.edit_message_text("I can only remember text messages.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            return

        if "gossip" in prompt.lower():
            gossip_list = load_gossip().get(chat_id_str, [])
            if gossip_list:
                random_gossip = random.choice(gossip_list)
                await global_context.bot.edit_message_text(f"Remember when {random_gossip['author']} said: \"{random_gossip['text']}\"?", chat_id=event.chat_id, message_id=thinking_message.message_id)
            else:
                await global_context.bot.edit_message_text("Nothing juicy to share yet.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            return

        # Sticker creation command
        if "sticker of" in prompt.lower():
            sticker_prompt = re.sub(r'(?i)sticker of\s*', '', prompt).strip()
            if not sticker_prompt:
                await global_context.bot.edit_message_text("What kind of sticker? Usage: `/ai sticker of a happy cat`", chat_id=event.chat_id, message_id=thinking_message.message_id)
                return

            await global_context.bot.edit_message_text(f"🎨 Creating sticker: `{sticker_prompt}`...", chat_id=event.chat_id, message_id=thinking_message.message_id)
            
            # Generate image using Samurai API
            image_bytes = await generate_sticker_image(sticker_prompt)
            
            if image_bytes:
                # Convert to sticker format
                sticker_bytes = await convert_to_sticker(image_bytes)
                
                if sticker_bytes:
                    try:
                        await global_context.bot.send_sticker(
                            chat_id=event.chat_id, 
                            sticker=sticker_bytes
                        )
                        await thinking_message.delete()
                    except errors.RPCError as e:
                        logger.error(f"Failed to send sticker: {e}")
                        await global_context.bot.edit_message_text(
                            f"Failed to send sticker: {e.message}", 
                            chat_id=event.chat_id, 
                            message_id=thinking_message.message_id
                        )
                    except Exception as e:
                        logger.error(f"Unexpected error sending sticker: {e}")
                        await global_context.bot.edit_message_text(
                            "An unexpected error occurred sending the sticker.", 
                            chat_id=event.chat_id, 
                            message_id=thinking_message.message_id
                        )
                else:
                    await global_context.bot.edit_message_text(
                        "Failed to convert image to sticker format.", 
                        chat_id=event.chat_id, 
                        message_id=thinking_message.message_id
                    )
            else:
                await global_context.bot.edit_message_text(
                    "Failed to generate the sticker image.", 
                    chat_id=event.chat_id, 
                    message_id=thinking_message.message_id
                )
            return  # Sticker generation finished
        
        # --- NEW: Video Generation Command ---
        if "video of" in prompt.lower() or "make a video of" in prompt.lower():
            video_prompt = re.sub(r'(?i)(make a )?video of\s*', '', prompt).strip()
            if not video_prompt:
                await global_context.bot.edit_message_text("What kind of video? Usage: `/ai video of a cat chasing a laser`", chat_id=event.chat_id, message_id=thinking_message.message_id)
                return

            await global_context.bot.edit_message_text(f"🎬 Generating video: `{video_prompt}` (This may take a while)...", chat_id=event.chat_id, message_id=thinking_message.message_id)
            video_bytes = await generate_video_from_text(video_prompt)

            if video_bytes:
                try:
                    # Sending the video
                    await global_context.bot.send_video(chat_id=event.chat_id, video=video_bytes, caption=f"🎥 Video for: `{video_prompt}`", read_timeout=300, write_timeout=300, connect_timeout=300) # Add timeouts
                    await thinking_message.delete()
                except errors.RPCError as e:
                    logger.error(f"Failed to send video: {e}")
                    await global_context.bot.edit_message_text(f"Failed to send video: {e.message}", chat_id=event.chat_id, message_id=thinking_message.message_id)
                except Exception as e:
                     logger.error(f"Unexpected error sending video: {e}")
                     await global_context.bot.edit_message_text("An unexpected error occurred sending the video.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            else:
                await global_context.bot.edit_message_text("Failed to generate the video.", chat_id=event.chat_id, message_id=thinking_message.message_id)
            return # Video generation finished
        
        # Default action: Web Search + AI Answer
        await global_context.bot.edit_message_text("🔎 Searching the web...", chat_id=event.chat_id, message_id=thinking_message.message_id)
        search_results = await execute_web_search(prompt)
        
        # Construct a more detailed prompt for the AI
        persona_prompt = "You are AI618, a witty and clever AI. Use your personality."
        final_prompt = (
            f"{persona_prompt} Answer the user's prompt based on the provided web search results. "
            f"If the search results seem irrelevant or failed ('Error:', 'No web results'), answer based on your own knowledge.\n\n"
            f"User Prompt: {prompt}\n\nWeb Search Results:\n{search_results}"
        )
        messages = [{"role": "system", "content": persona_prompt}, {"role": "user", "content": final_prompt}]
        
        await global_context.bot.edit_message_text("🧠 Thinking...", chat_id=event.chat_id, message_id=thinking_message.message_id)
        response = await get_typegpt_response(messages)
        await send_final_response(update, context, response, thinking_message, prompt)

    except Exception as e:
        logger.error(f"Smart AI Handler failed catastrophically: {e}", exc_info=True)
        try:
            await global_context.bot.edit_message_text("An unexpected error occurred processing your request.", chat_id=event.chat_id, message_id=thinking_message.message_id)
        except errors.RPCError: pass # Ignore if original message deleted


async def master_text_handler(event) -> None:
    # Ensure message and text exist before proceeding
    if not update.message or not event.text:
        return

    chat_id = str(event.chat_id)
    session = trivia_sessions.get(chat_id)

    # --- LOCKDOWN MODE: If trivia is active, only game logic runs ---
    if session and session.get("state") in ["registering", "asking"]:
        await trivia_master_handler(update, context)
        return # Block all other AI features during the game.

    # --- Priority 2: Standard AI Replies & Mentions (only if no game is active) ---
    config = load_config()
    # Check if AI features are enabled for this chat before processing replies/mentions
    if config.get("ai_enabled_config", {}).get(chat_id, False):
        if event.reply_to_msg_id and await event.get_reply_message() and event.reply_to_msg_id and await event.get_reply_message().from_user and event.reply_to_msg_id and await event.get_reply_message().from_user.id == global_context.bot.id:
            await reply_handler(update, context)
            return

        if re.search(r'(?i)\bAI618\b', event.text):
            await name_mention_handler(update, context)
            return

    # --- Priority 3: Proactive & Background Tasks (run regardless of AI status for history, but check AI status for reactions) ---
    await proactive_reaction_handler(update, context) # This function checks AI status internally
    await history_capture_handler(update, context) # Always capture history


async def trivia_master_handler(event) -> bool:
    """Handles player registration ('me', 'all in') during the registration phase."""
    chat_id = str(event.chat_id)
    session = trivia_sessions.get(chat_id)

    # Only act during registration state
    if not session or session.get("state") != "registering":
        return False

    user = event.sender
    text = event.text.lower().strip()

    # Check if it's a reply to the registration message
    if event.reply_to_msg_id and await event.get_reply_message() and event.reply_to_msg_id and await event.get_reply_message().message_id == session.get("registration_message_id"):
        if text == 'me':
            if user.id not in session["players"]:
                session["players"][user.id] = {"username": user.username or "", "first_name": user.first_name or "User", "score": 0}
                await event.reply(f"{user.first_name or 'User'} is in! ✅")
            else:
                await event.reply("You're already in!")
            return True # Message handled

        elif text == 'all in':
            if not session["players"]:
                await event.reply("We need at least one player to start!")
                return True # Message handled

            # Get player names for announcement
            player_list = []
            for p_data in session["players"].values():
                mention = f"@{p_data['username']}" if p_data['username'] else p_data['first_name']
                player_list.append(mention)

            await event.reply(f"Registration closed! Players: {', '.join(player_list)}. Let's begin!")
            # Delete registration message
            try: await global_context.bot.delete_message(chat_id, session["registration_message_id"])
            except errors.RPCError: pass
            
            # Start the game by asking the first question
            await ask_next_trivia_question(context, chat_id)
            return True # Message handled
            
    return False # Not a relevant registration message

async def reply_handler(event):
    # Ensure messages exist
    if not update.message or not event.text or not event.reply_to_msg_id and await event.get_reply_message() or not event.reply_to_msg_id and await event.get_reply_message().text: return
    
    thinking_message = await event.reply("...")
    # Use a consistent persona prompt
    persona = "You are AI618, a witty and clever AI. Respond in character."
    messages = [
        {"role": "system", "content": persona},
        {"role": "assistant", "content": event.reply_to_msg_id and await event.get_reply_message().text},
        {"role": "user", "content": event.text}
    ]
    response = await get_typegpt_response(messages)
    await send_final_response(update, context, response, thinking_message, "AI Reply")

async def name_mention_handler(event):
    if not update.message or not event.text: return

    thinking_message = await event.reply("...")
    persona = "You are AI618, a witty and clever AI. The user mentioned your name. Respond in character."
    messages = [
        {"role": "system", "content": persona},
        {"role": "user", "content": event.text}
    ]
    response = await get_typegpt_response(messages)
    await send_final_response(update, context, response, thinking_message, "AI Mention")

async def proactive_reaction_handler(event):
    # Only react if AI is on for the group
    config = load_config()
    chat_id = str(event.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False): return
    if not update.message or not event.text: return

    if random.random() < 0.45: # Reaction probability
        emoji_str = await get_emoji_reaction(event.text)
        if emoji_str:
            try:
                await global_context.bot.set_message_reaction(chat_id=event.chat_id, message_id=event.id, reaction=[ReactionTypeEmoji(emoji_str)])
                logger.info(f"Reacted with {emoji_str} in chat {chat_id}")
            except errors.RPCError as e:
                # Ignore common harmless errors or permission issues silently
                if "MESSAGE_NOT_MODIFIED" not in e.message and "REACTION_INVALID" not in e.message and "USER_IS_BLOCKED" not in e.message and "chat not found" not in e.message:
                    logger.warning(f"Failed to set reaction: {e.message}")
            except Exception as e:
                 logger.error(f"Unexpected error setting reaction: {e}")

async def history_capture_handler(event):
    # Ensure message and text exist
    if not update.message or not event.text: return

    chat_id = event.chat_id
    history = chat_histories.setdefault(chat_id, deque(maxlen=30)) # Store last 30 messages
    history.append(f"{event.sender.first_name or 'User'}: {event.text}")
    
    # Schedule random chat only if AI is enabled AND random chat is enabled for this group
    config = load_config()
    chat_id_str = str(chat_id)
    if config.get("ai_enabled_config", {}).get(chat_id_str, False) and \
       config.get("random_chat_config", {}).get(chat_id_str, True): # Default random ON if not set
        # Check existing jobs for this chat
        current_jobs = global_context.job_queue.get_jobs_by_name(f"random_chat_{chat_id}")
        if not current_jobs: # Only schedule if no job exists
             global_context.job_queue.run_once(random_chat_callback, random.uniform(300, 600), data={'chat_id': chat_id}, name=f"random_chat_{chat_id}")
             # active_random_jobs isn't strictly needed now if we check get_jobs_by_name
             logger.info(f"Scheduled random chat job for chat_id: {chat_id}")

async def random_chat_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data.get('chat_id')
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
                await global_context.bot.send_message(chat_id=chat_id, text=response)
                chat_histories[chat_id].clear() # Clear history after commenting
            except errors.RPCError as e:
                logger.error(f"Failed to send random chat message: {e}")
        else:
             logger.warning(f"Random chat AI failed to generate response for chat {chat_id}")
    else:
        logger.info(f"Skipping random chat for {chat_id}, not enough history.")




async def help_command(event):
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
        "`/react` (Reply to msg) - Force AI reaction\n"
        "`/videoedit [prompt]` (Reply to image) - Generate video from image\n"
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
        "**Proactive Calls** (Admin)\n"
        "`/callon` - Enable proactive call participation\n"
        "`/calloff` - Disable proactive call participation\n"
        "`/callstatus` - Check call feature status\n"
        "`/callquiet HH:MM HH:MM` - Set quiet hours (start end)\n"
        "`/callconfig [min_participants]` - Configure call settings\n\n"
        "**Moderation** (Requires Mod ON & Admin)\n"
        "`/ban`, `/mute`, `/unmute` (Reply to user)\n"
        "`/delete` (Reply to message)\n"
        "`/lock`, `/unlock` (Chat permissions)"
    )
    await event.reply(help_text, parse_mode='Markdown')

async def force_react_command(event):
    # Ensure message exists
    if not update.message: return
    replied_message = event.reply_to_msg_id and await event.get_reply_message()
    if not replied_message or not replied_message.text:
        await event.reply("Reply to a text message to react.")
        return
    emoji_str = await get_emoji_reaction(replied_message.text)
    if emoji_str:
        try:
            await global_context.bot.set_message_reaction(chat_id=event.chat_id, message_id=replied_message.message_id, reaction=[ReactionTypeEmoji(emoji_str)])
            # Delete the command message
            try: await event.delete()
            except errors.RPCError: pass
        except errors.RPCError as e:
            logger.warning(f"Failed to force reaction: {e.message}")
            # Don't send error message to user, just log

async def toggle_audio_mode_handler(event):
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
         await event.reply("Only admins can toggle audio mode.")
         return
    chat_id = str(event.chat_id)
    config = load_config()
    is_enabled = config.setdefault("audio_mode_config", {}).get(chat_id, False)
    config["audio_mode_config"][chat_id] = not is_enabled
    save_config(config)
    status = "ON" if not is_enabled else "OFF"
    await event.reply(f"🎤 Audio mode is now **{status}**.", parse_mode='Markdown')

# --- Other Command Handlers ---

async def chem_handler(event) -> None:
    if not update.message: return
    smiles = " ".join(event.text.split()[1:])
    if not smiles:
        await event.reply("Provide a SMILES string. Usage: `/chem CCO`")
        return
    mol = await asyncio.to_thread(Chem.MolFromSmiles, smiles) # Run RDKit in thread
    if mol is None:
        await event.reply("Invalid SMILES string.")
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
        await event.respond(file=png_buffer, caption=f"`{smiles}`", parse_mode='md')
    except Exception as e:
        logger.error(f"RDKit chem handler failed: {e}")
        await event.reply("Error generating molecule image.")

async def latex_handler(event) -> None:
    if not update.message: return
    latex_code = " ".join(event.text.split()[1:])
    if not latex_code:
        await event.reply("Provide a LaTeX expression. Usage: `/tex E = mc^2`")
        return
    try:
        url = f"https://latex.codecogs.com/png.latex?%5Cdpi{{300}}%20{httpx.utils.quote(latex_code)}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0) # Increased timeout
            if response.status_code == 200:
                await event.respond(file=response.content, caption=f"`{latex_code}`", parse_mode='Markdown')
            else:
                await event.reply(f"Failed to render LaTeX (Status: {response.status_code}). Check syntax?")
    except httpx.TimeoutException:
         await event.reply("LaTeX rendering service timed out.")
    except Exception as e:
        logger.error(f"LaTeX handler failed: {e}")
        await event.reply("Error rendering LaTeX.")

async def get_chat_id(event) -> None:
    if not update.message: return
    await event.reply(f"This Chat ID is: `{event.chat_id}`", parse_mode='Markdown')

async def remember_command(event) -> None:
    if not update.message: return
    text = " ".join(event.text.split()[1:])
    if '=' not in text:
        await event.reply("Usage: `/remember topic = fact`")
        return
    topic, fact = [x.strip() for x in text.split('=', 1)]
    if not topic or not fact:
        await event.reply("Both topic and fact are required.")
        return
    memory = load_memory()
    memory[topic.lower()] = fact
    save_memory(memory)
    await event.reply(f"👍 Okay, remembered that '{topic}' is '{fact}'.")

async def recall_command(event) -> None:
    if not update.message: return
    if not event.text.split()[1:]:
        memory = load_memory()
        if not memory:
            await event.reply("I haven't remembered anything yet.")
            return
        topics = ", ".join(memory.keys())
        await event.reply(f"Topics I remember: {topics}")
        return
    topic = " ".join(event.text.split()[1:]).lower()
    memory = load_memory()
    fact = memory.get(topic)
    if fact:
        await event.reply(f"'{topic}': {fact}")
    else:
        await event.reply(f"I don't remember anything about '{topic}'.")

async def forget_command(event) -> None:
    if not update.message: return
    if not event.text.split()[1:]:
        await event.reply("What should I forget? Usage: `/forget topic`")
        return
    topic = " ".join(event.text.split()[1:]).lower()
    memory = load_memory()
    if topic in memory:
        del memory[topic]
        save_memory(memory)
        await event.reply(f"👌 Okay, forgot about '{topic}'.")
    else:
        await event.reply(f"I didn't know anything about '{topic}' anyway.")

async def summarize_command(event) -> None:
    if not update.message: return
    chat_id = event.chat_id
    if chat_id not in chat_histories or len(chat_histories[chat_id]) < 3: # Lowered threshold
        await event.reply("Not enough recent chat history to summarize.")
        return
    transcript = "\n".join(chat_histories[chat_id])
    prompt = f"Summarize the following recent group chat transcript concisely in a few bullet points:\n\n{transcript}"
    thinking_message = await event.reply("Summarizing...")
    summary = await get_typegpt_response([{"role": "system", "content": "You summarize chat logs into key points."}, {"role": "user", "content": prompt}])
    await send_final_response(update, context, summary, thinking_message, "Chat Summary")

async def studypoll_command(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can create polls.")
        return
    try:
        # Use shlex to handle quotes correctly
        args = shlex.split(" ".join(event.text.split()[1:]))
        if len(args) < 3 or len(args) > 11: # Question + 2-10 options
            await event.reply('Usage: /studypoll "Question" "Option 1" "Option 2" ... (Max 10 options)')
            return
        question = args[0]
        options = args[1:]
        await global_context.bot.send_poll(chat_id=event.chat_id, question=question, options=options, is_anonymous=False)
    except ValueError as e: # Catch shlex errors
         await event.reply(f"Error parsing arguments (check your quotes?): {e}")
    except Exception as e:
        await event.reply(f"Error creating poll: {e}")

async def aipoll_handler(event) -> None:
    if not update.message: return
    await event.reply("Use `/ai make a poll about [topic]` instead.")

async def web_handler(event) -> None:
    if not update.message: return
    await event.reply("Use `/ai [your query]` for web search.")

async def nanoedit_handler(event) -> None:
    if not update.message: return
    config = load_config()
    chat_id = str(event.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False):
        await event.reply("AI is off for this group.")
        return

    replied_message = event.reply_to_msg_id and await event.get_reply_message()
    if not (replied_message and replied_message.photo):
        await event.reply("Reply to an image with /nanoedit to use this command.")
        return

    prompt = " ".join(event.text.split()[1:])
    if not prompt: prompt = "Describe this image."

    thinking_message = await event.reply("Processing image with Nano...")

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
                        await global_context.bot.send_photo(chat_id=event.chat_id, photo=image_bytes, caption=f"🖼️ Result: `{prompt}`", parse_mode='Markdown')
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
            await global_context.bot.edit_message_text("Image edit failed, trying description...", chat_id=event.chat_id, message_id=thinking_message.message_id)
            # --- FALLBACK: Text-based vision ---
            text_response = await get_typegpt_gemini_vision_response(messages) # Or Baidu
            if not text_response:
                text_response = await get_baidu_ernie_vision_response(messages)
            
            if text_response:
                 await send_final_response(update, context, text_response, thinking_message, prompt)
            else:
                 await global_context.bot.edit_message_text("All fallbacks failed.", chat_id=event.chat_id, message_id=thinking_message.message_id)
    
    except Exception as e:
        logger.error(f"Nanoedit handler failed catastrophically: {e}")
        await global_context.bot.edit_message_text("Command Failed.", chat_id=event.chat_id, message_id=thinking_message.message_id)


async def askit_handler(event) -> None:
    if not update.message: return
    config = load_config()
    chat_id = str(event.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False):
        await event.reply("AI is off for this group.")
        return

    replied_message = event.reply_to_msg_id and await event.get_reply_message()
    if not (replied_message and replied_message.photo):
        await event.reply("Reply to an image with /askit.")
        return

    prompt = " ".join(event.text.split()[1:]) or "Describe this image in detail."
    thinking_message = await event.reply("Analyzing image...")

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
            await global_context.bot.edit_message_text("All vision models failed.", chat_id=event.chat_id, message_id=thinking_message.message_id)

    except Exception as e:
        logger.error(f"Askit handler failed: {e}")
        await global_context.bot.edit_message_text("Image analysis failed.", chat_id=event.chat_id, message_id=thinking_message.message_id)

async def videoedit_handler(event) -> None:
    """Generate video from image using Replicate's free/wan-2.1-i2v-14b-720p model."""
    if not update.message: 
        return
    
    config = load_config()
    chat_id = str(event.chat_id)
    if not config.get("ai_enabled_config", {}).get(chat_id, False):
        await event.reply("AI is off for this group.")
        return
    
    # Check if replying to a message with an image
    replied_message = event.reply_to_msg_id and await event.get_reply_message()
    if not (replied_message and replied_message.photo):
        await event.reply("Reply to an image with /videoedit \"prompt\" to generate a video.")
        return
    
    # Extract prompt from command arguments
    prompt = " ".join(event.text.split()[1:])
    if not prompt:
        await event.reply("Please provide a prompt. Usage: /videoedit \"your prompt here\"")
        return
    
    # Check if Replicate API key is configured
    if not REPLICATE_API_KEY:
        await event.reply("Video generation is not configured (missing API key).")
        return
    
    thinking_message = await event.reply("🎬 Generating video... This may take a few minutes.")
    
    try:
        # Download the image from Telegram
        logger.info(f"Downloading image for video generation with prompt: {prompt}")
        photo_file = await replied_message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert bytes to a file-like object for Replicate
        image_io = io.BytesIO(photo_bytes)
        
        # Use Replicate to generate video
        logger.info("Calling Replicate API for image-to-video generation...")
        
        def run_replicate_i2v():
            """Run Replicate image-to-video in a blocking manner."""
            try:
                output = replicate.run(
                    "free/wan-2.1-i2v-14b-720p",
                    input={
                        "image": image_io,
                        "prompt": prompt
                    }
                )
                return output
            except Exception as e:
                logger.error(f"Replicate API error: {e}")
                return None
        
        # Run in a separate thread to avoid blocking
        output = await asyncio.to_thread(run_replicate_i2v)
        
        if not output:
            await global_context.bot.edit_message_text(
                "❌ Video generation failed. The API returned no output.",
                chat_id=event.chat_id,
                message_id=thinking_message.message_id
            )
            return
        
        # Handle different output formats from Replicate
        video_url = None
        if isinstance(output, str):
            video_url = output
        elif isinstance(output, list) and len(output) > 0:
            video_url = output[0] if isinstance(output[0], str) else str(output[0])
        else:
            logger.warning(f"Unexpected output type: {type(output)}, trying to convert to string")
            try:
                video_url = str(output)
            except:
                pass
        
        if not video_url or not video_url.startswith('http'):
            logger.error(f"Invalid video URL from Replicate: {video_url}")
            await global_context.bot.edit_message_text(
                "❌ Video generation failed. Invalid response from API.",
                chat_id=event.chat_id,
                message_id=thinking_message.message_id
            )
            return
        
        logger.info(f"Downloading generated video from: {video_url}")
        await global_context.bot.edit_message_text(
            "📥 Downloading video...",
            chat_id=event.chat_id,
            message_id=thinking_message.message_id
        )
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            video_response = await client.get(video_url)
            video_response.raise_for_status()
            video_bytes = video_response.content
        
        logger.info(f"Video downloaded successfully. Size: {len(video_bytes)} bytes")
        
        # Send the video back to the chat
        await global_context.bot.send_video(
            chat_id=event.chat_id,
            video=video_bytes,
            caption=f"🎬 Generated video\nPrompt: {prompt}",
            reply_to_message_id=replied_message.message_id
        )
        
        # Delete the thinking message
        try:
            await thinking_message.delete()
        except errors.RPCError:
            pass
        
        logger.info("Video sent successfully!")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading video: {e}")
        await global_context.bot.edit_message_text(
            "❌ Failed to download the generated video.",
            chat_id=event.chat_id,
            message_id=thinking_message.message_id
        )
    except httpx.TimeoutException:
        logger.error("Timeout while generating or downloading video")
        await global_context.bot.edit_message_text(
            "⏱️ Video generation timed out. Please try again with a simpler prompt.",
            chat_id=event.chat_id,
            message_id=thinking_message.message_id
        )
    except Exception as e:
        logger.error(f"Video generation handler failed: {e}", exc_info=True)
        try:
            await global_context.bot.edit_message_text(
                f"❌ Video generation failed: {str(e)}",
                chat_id=event.chat_id,
                message_id=thinking_message.message_id
            )
        except errors.RPCError:
            pass

async def simple_ai_handler(event) -> None:
    if not update.message: return
    # Keep this for backward compatibility or simpler tasks if needed
    prompt = " ".join(event.text.split()[1:])
    if not prompt:
        await event.reply("Please provide a prompt.")
        return
    thinking_message = await event.reply("Thinking...")
    messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    response = await get_typegpt_response(messages) # Use the main chain
    await send_final_response(update, context, response, thinking_message, prompt)
    
# --- Settings and Moderation Command Handlers ---

async def turn_ai_on(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id)
    config = load_config(); config.setdefault("ai_enabled_config", {})[chat_id] = True; save_config(config)
    await event.reply("✅ AI features **ON**.", parse_mode='Markdown')

async def turn_ai_off(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id); config = load_config()
    config.setdefault("ai_enabled_config", {})[chat_id] = False; save_config(config)
    await event.reply("❌ AI features **OFF**.", parse_mode='Markdown')

async def check_ai_status(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id); config = load_config()
    status = "ON" if config.get("ai_enabled_config", {}).get(chat_id, False) else "OFF"
    await event.reply(f"ℹ️ AI features are **{status}**.", parse_mode='Markdown')

async def turn_random_chat_on(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id); config = load_config()
    config.setdefault("random_chat_config", {})[chat_id] = True; save_config(config)
    await event.reply("✅ Random chat **ON**.", parse_mode='Markdown')

async def turn_random_chat_off(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id); config = load_config()
    config.setdefault("random_chat_config", {})[chat_id] = False; save_config(config)
    await event.reply("❌ Random chat **OFF**.", parse_mode='Markdown')

async def check_random_status(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    chat_id = str(event.chat_id); config = load_config()
    status = "ON" if config.get("random_chat_config", {}).get(chat_id, True) else "OFF" # Default ON
    await event.reply(f"ℹ️ Random chat is **{status}**.", parse_mode='Markdown')

async def test_random_handler(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    await event.reply("Triggering random chat logic now...")
    # Schedule immediately
    global_context.job_queue.run_once(random_chat_callback, 0, data={"chat_id": event.chat_id})

async def turn_moderation_on(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    config = load_config(); config["moderation_enabled"] = True; save_config(config)
    await event.reply("✅ Moderation commands **ON**.", parse_mode='Markdown')

async def turn_moderation_off(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): return
    config = load_config(); config["moderation_enabled"] = False; save_config(config)
    await event.reply("❌ Moderation commands **OFF**.", parse_mode='Markdown')

async def ban_user(event) -> None:
    if not update.message: return
    config = load_config()
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    if not event.reply_to_msg_id and await event.get_reply_message(): await event.reply("Reply to ban."); return
    target_user = event.reply_to_msg_id and await event.get_reply_message().from_user
    try:
        await global_context.bot.ban_chat_member(event.chat_id, target_user.id)
        await event.reply(f"Banned {target_user.first_name or 'User'}.")
    except Exception as e: await event.reply(f"Failed to ban: {e}")

async def mute_user(event) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    if not event.reply_to_msg_id and await event.get_reply_message(): await event.reply("Reply to mute."); return
    target_user = event.reply_to_msg_id and await event.get_reply_message().from_user
    try:
        await global_context.bot.restrict_chat_member(event.chat_id, target_user.id, ChatPermissions(can_send_messages=False))
        await event.reply(f"Muted {target_user.first_name or 'User'}.")
    except Exception as e: await event.reply(f"Failed to mute: {e}")

async def unmute_user(event) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    if not event.reply_to_msg_id and await event.get_reply_message(): await event.reply("Reply to unmute."); return
    target_user = event.reply_to_msg_id and await event.get_reply_message().from_user
    try:
        # Restore default permissions (adjust if your group has specific defaults)
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True, can_send_polls=True, can_invite_users=True) # Common defaults
        await global_context.bot.restrict_chat_member(event.chat_id, target_user.id, perms)
        await event.reply(f"Unmuted {target_user.first_name or 'User'}.")
    except Exception as e: await event.reply(f"Failed to unmute: {e}")

async def delete_message(event) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    if not event.reply_to_msg_id and await event.get_reply_message(): await event.reply("Reply to delete."); return
    try:
        await global_context.bot.delete_message(event.chat_id, event.reply_to_msg_id and await event.get_reply_message().message_id)
        # Delete the command message too for cleanliness
        try: await event.delete()
        except errors.RPCError: pass # Ignore if already gone
    except Exception as e: await event.reply(f"Failed to delete: {e}")

async def lock_chat(event) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    try:
        await global_context.bot.set_chat_permissions(event.chat_id, ChatPermissions(can_send_messages=False))
        await event.reply("🔒 Chat locked.")
    except Exception as e: await event.reply(f"Failed to lock: {e}")

async def unlock_chat(event) -> None:
    if not update.message: return
    config = load_config();
    if not config.get("moderation_enabled", True): await event.reply("Mod commands off."); return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    try:
        # Restore default permissions (adjust if needed)
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True)
        await global_context.bot.set_chat_permissions(event.chat_id, perms)
        await event.reply("🔓 Chat unlocked.")
    except Exception as e: await event.reply(f"Failed to unlock: {e}")

async def set_reminder_time_handler(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id): await event.reply("Admins only."); return
    if not event.text.split()[1:]: await event.reply("Usage: /time HH:MM (24-hour IST)"); return
    try:
        new_time_str = event.text.split()[1:][0]
        new_time_obj = datetime.strptime(new_time_str, "%H:%M").time()
        config = load_config(); config["reminder_time"] = new_time_str; save_config(config)
        # Reschedule job
        current_jobs = global_context.job_queue.get_jobs_by_name("daily_reminder")
        for job in current_jobs: job.schedule_removal()
        reminder_time = time(hour=new_time_obj.hour, minute=new_time_obj.minute, tzinfo=pytz.timezone('Asia/Kolkata'))
        global_context.job_queue.run_daily(send_daily_reminder, time=reminder_time, name="daily_reminder")
        await event.reply(f"✅ Reminder time updated to {new_time_str} IST.")
    except ValueError: await event.reply("Invalid time format. Use HH:MM.")
    except Exception as e: await event.reply(f"Error setting time: {e}")

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
            await global_context.bot.send_message(chat_id=TARGET_CHAT_ID, text=message, parse_mode='Markdown')
            logger.info(f"Sent daily reminder to {TARGET_CHAT_ID}")
        else:
            logger.info("No relevant dates left for daily reminder.")
            # Optionally remove the job if no dates are left
            # context.job.schedule_removal()
    except Exception as e: logger.error(f"Failed to send daily reminder: {e}")

# --- Proactive Call Command Handlers ---

async def turn_proactive_calls_on(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can toggle proactive call features.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "proactive_call_config" not in config:
        config["proactive_call_config"] = {}
    
    if chat_id not in config["proactive_call_config"]:
        config["proactive_call_config"][chat_id] = {}
    
    config["proactive_call_config"][chat_id]["enabled"] = True
    config["proactive_call_config"][chat_id].setdefault("min_participants", 2)
    
    save_config(config)
    
    await event.reply(
        "✅ **Proactive call participation is now ON.**\n\n"
        "The bot will now:\n"
        "• Listen to voice messages in calls\n"
        "• Transcribe speech to text\n"
        "• Respond contextually when appropriate\n\n"
        "Configure with `/callconfig` or set quiet hours with `/callquiet`.",
        parse_mode='Markdown'
    )

async def turn_proactive_calls_off(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can toggle proactive call features.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "proactive_call_config" not in config:
        config["proactive_call_config"] = {}
    
    if chat_id not in config["proactive_call_config"]:
        config["proactive_call_config"][chat_id] = {}
    
    config["proactive_call_config"][chat_id]["enabled"] = False
    save_config(config)
    
    # Clean up active call state
    if chat_id in active_calls:
        del active_calls[chat_id]
    
    await event.reply("❌ **Proactive call participation is now OFF.**", parse_mode='Markdown')

async def check_proactive_calls_status(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can check call status.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    call_config = config.get("proactive_call_config", {}).get(chat_id, {})
    is_enabled = call_config.get("enabled", False)
    min_participants = call_config.get("min_participants", 2)
    
    quiet_hours = config.get("call_quiet_hours", {}).get(chat_id, {})
    quiet_start = quiet_hours.get("start", "Not set")
    quiet_end = quiet_hours.get("end", "Not set")
    
    status_text = (
        f"ℹ️ **Proactive Call Status**\n\n"
        f"**Enabled:** {'✅ Yes' if is_enabled else '❌ No'}\n"
        f"**Min Participants:** {min_participants}\n"
        f"**Quiet Hours:** {quiet_start} - {quiet_end}\n"
    )
    
    if chat_id in active_calls:
        call_state = active_calls[chat_id]
        transcript_count = len(call_state.get("transcript", []))
        error_count = call_state.get("error_count", 0)
        status_text += f"\n**Current Call State:**\n"
        status_text += f"• Transcripts: {transcript_count}\n"
        status_text += f"• Errors: {error_count}\n"
    
    await event.reply(status_text, parse_mode='Markdown')

async def set_call_quiet_hours(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can set quiet hours.")
        return
    
    if len(event.text.split()[1:]) != 2:
        await event.reply("Usage: `/callquiet HH:MM HH:MM` (start time and end time in 24-hour format)")
        return
    
    try:
        start_str = event.text.split()[1:][0]
        end_str = event.text.split()[1:][1]
        
        # Validate time format
        datetime.strptime(start_str, "%H:%M")
        datetime.strptime(end_str, "%H:%M")
        
        chat_id = str(event.chat_id)
        config = load_config()
        
        if "call_quiet_hours" not in config:
            config["call_quiet_hours"] = {}
        
        config["call_quiet_hours"][chat_id] = {
            "start": start_str,
            "end": end_str
        }
        
        save_config(config)
        
        await event.reply(
            f"✅ Quiet hours set: **{start_str} to {end_str}** (IST)\n"
            f"The bot will not participate in calls during these hours.",
            parse_mode='Markdown'
        )
    
    except ValueError:
        await event.reply("Invalid time format. Use HH:MM (24-hour format).")
    except Exception as e:
        logger.error(f"Error setting quiet hours: {e}")
        await event.reply("Error setting quiet hours.")

async def configure_call_settings(event) -> None:
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can configure call settings.")
        return
    
    if not event.text.split()[1:]:
        await event.reply("Usage: `/callconfig [min_participants]`\nExample: `/callconfig 3`")
        return
    
    try:
        min_participants = int(event.text.split()[1:][0])
        
        if min_participants < 1:
            await event.reply("Minimum participants must be at least 1.")
            return
        
        chat_id = str(event.chat_id)
        config = load_config()
        
        if "proactive_call_config" not in config:
            config["proactive_call_config"] = {}
        
        if chat_id not in config["proactive_call_config"]:
            config["proactive_call_config"][chat_id] = {"enabled": False}
        
        config["proactive_call_config"][chat_id]["min_participants"] = min_participants
        save_config(config)
        
        await event.reply(
            f"✅ Call configuration updated:\n"
            f"**Minimum participants:** {min_participants}",
            parse_mode='Markdown'
        )
    
    except ValueError:
        await event.reply("Invalid number. Please provide a valid integer.")
    except Exception as e:
        logger.error(f"Error configuring call settings: {e}")
        await event.reply("Error updating call configuration.")

async def joincall_command(event) -> None:
    """Manually join a voice chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can control call participation.")
        return
    
    chat_id_int = event.chat_id
    
    # Check if API credentials are configured
    if not API_ID or not API_HASH:
        await event.reply(
            "❌ Call features not configured.\n"
            "Please set API_ID and API_HASH environment variables."
        )
        return
    
    # Check if already in call
    if await is_in_call(chat_id_int):
        await event.reply("✅ Already in the voice chat.")
        return
    
    status_msg = await event.reply("🔄 Joining voice chat...")
    
    try:
        success = await join_voice_chat(chat_id_int, auto_join=False)
        
        if success:
            await status_msg.edit_text("✅ Successfully joined the voice chat!")
        else:
            await status_msg.edit_text(
                "❌ Failed to join voice chat.\n"
                "Make sure a voice chat is active in this group."
            )
    
    except Exception as e:
        logger.error(f"Error in joincall command: {e}", exc_info=True)
        await status_msg.edit_text("❌ Error joining voice chat.")

async def leavecall_command(event) -> None:
    """Manually leave a voice chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can control call participation.")
        return
    
    chat_id_int = event.chat_id
    
    # Check if in call
    if not await is_in_call(chat_id_int):
        await event.reply("Not currently in a voice chat.")
        return
    
    status_msg = await event.reply("🔄 Leaving voice chat...")
    
    try:
        success = await leave_voice_chat(chat_id_int)
        
        if success:
            await status_msg.edit_text("✅ Successfully left the voice chat.")
        else:
            await status_msg.edit_text("⚠️ Attempted to leave voice chat (may have already left).")
    
    except Exception as e:
        logger.error(f"Error in leavecall command: {e}", exc_info=True)
        await status_msg.edit_text("❌ Error leaving voice chat.")

async def callinfo_command(event) -> None:
    """Show detailed call state information."""
    if not update.message: return
    
    chat_id_int = event.chat_id
    call_state = await get_call_state(chat_id_int)
    
    state = call_state.get("state", "idle")
    error_count = call_state.get("error_count", 0)
    transcript_count = len(call_state.get("transcript", []))
    join_time = call_state.get("join_time")
    
    # Check pytgcalls instance
    chat_id_str = str(chat_id_int)
    has_instance = chat_id_str in pytgcalls_instances
    
    status_text = "🎙️ **Call Framework Status**\n\n"
    status_text += f"**State:** {state}\n"
    status_text += f"**In Call:** {'✅ Yes' if await is_in_call(chat_id_int) else '❌ No'}\n"
    status_text += f"**pytgcalls Instance:** {'✅ Active' if has_instance else '❌ Not initialized'}\n"
    status_text += f"**Transcript Buffer:** {transcript_count} messages\n"
    status_text += f"**Error Count:** {error_count}\n"
    
    if join_time:
        duration = datetime.now() - join_time
        minutes = int(duration.total_seconds() / 60)
        status_text += f"**Call Duration:** {minutes} minutes\n"
    
    # Check Telethon status
    status_text += f"\n**Telethon Client:** {'✅ Connected' if telethon_client else '❌ Not initialized'}\n"
    
    await event.reply(status_text, parse_mode='Markdown')

# --- TTS/STT Configuration Commands ---

async def ttson(event) -> None:
    """Enable TTS for this chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can enable TTS.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "tts_config" not in config:
        config["tts_config"] = {}
    
    if chat_id not in config["tts_config"]:
        config["tts_config"][chat_id] = {}
    
    config["tts_config"][chat_id]["enabled"] = True
    save_config(config)
    
    await event.reply("✅ TTS enabled for this chat. Bot will speak responses during calls.")

async def ttsoff(event) -> None:
    """Disable TTS for this chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can disable TTS.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "tts_config" not in config:
        config["tts_config"] = {}
    
    if chat_id not in config["tts_config"]:
        config["tts_config"][chat_id] = {}
    
    config["tts_config"][chat_id]["enabled"] = False
    save_config(config)
    
    await event.reply("✅ TTS disabled for this chat.")

async def ttsconfig(event) -> None:
    """Configure TTS voice and rate. Usage: /ttsconfig [voice] [rate]"""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can configure TTS.")
        return
    
    if not event.text.split()[1:]:
        await event.reply(
            "Usage: `/ttsconfig [voice] [rate]`\n"
            "Example: `/ttsconfig en-US-AriaNeural +10%`\n"
            "Common voices: en-US-AriaNeural, en-GB-SoniaNeural, en-US-GuyNeural\n"
            "Rate: -50% to +100% (default +0%)",
            parse_mode='Markdown'
        )
        return
    
    try:
        voice = event.text.split()[1:][0] if len(event.text.split()[1:]) > 0 else EDGE_TTS_VOICE
        rate = event.text.split()[1:][1] if len(event.text.split()[1:]) > 1 else EDGE_TTS_RATE
        
        chat_id = str(event.chat_id)
        config = load_config()
        
        if "tts_config" not in config:
            config["tts_config"] = {}
        
        if chat_id not in config["tts_config"]:
            config["tts_config"][chat_id] = {"enabled": False}
        
        config["tts_config"][chat_id]["voice"] = voice
        config["tts_config"][chat_id]["rate"] = rate
        save_config(config)
        
        await event.reply(
            f"✅ TTS configuration updated:\n"
            f"**Voice:** {voice}\n"
            f"**Rate:** {rate}",
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error configuring TTS: {e}")
        await event.reply("Error updating TTS configuration.")

async def ttsstatus(event) -> None:
    """Check TTS status for this chat."""
    if not update.message: return
    
    chat_id = str(event.chat_id)
    config = load_config()
    tts_config = config.get("tts_config", {}).get(chat_id, {})
    
    enabled = tts_config.get("enabled", False)
    voice = tts_config.get("voice", EDGE_TTS_VOICE)
    rate = tts_config.get("rate", EDGE_TTS_RATE)
    
    status = "🔊 **Enabled**" if enabled else "🔇 **Disabled**"
    
    await event.reply(
        f"TTS Status: {status}\n"
        f"Voice: {voice}\n"
        f"Rate: {rate}",
        parse_mode='Markdown'
    )

async def stton(event) -> None:
    """Enable STT for this chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can enable STT.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "stt_config" not in config:
        config["stt_config"] = {}
    
    if chat_id not in config["stt_config"]:
        config["stt_config"][chat_id] = {}
    
    config["stt_config"][chat_id]["enabled"] = True
    save_config(config)
    
    # Initialize Whisper model in background
    asyncio.create_task(initialize_whisper_model())
    
    await event.reply("✅ STT enabled for this chat. Send voice messages to transcribe them.")

async def sttoff(event) -> None:
    """Disable STT for this chat."""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can disable STT.")
        return
    
    chat_id = str(event.chat_id)
    config = load_config()
    
    if "stt_config" not in config:
        config["stt_config"] = {}
    
    if chat_id not in config["stt_config"]:
        config["stt_config"][chat_id] = {}
    
    config["stt_config"][chat_id]["enabled"] = False
    save_config(config)
    
    await event.reply("✅ STT disabled for this chat.")

async def sttconfig(event) -> None:
    """Configure STT language. Usage: /sttconfig [language]"""
    if not update.message: return
    if not await is_user_admin(event.chat_id, event.sender.id):
        await event.reply("Only admins can configure STT.")
        return
    
    if not event.text.split()[1:]:
        await event.reply(
            "Usage: `/sttconfig [language]`\n"
            "Example: `/sttconfig en` or `/sttconfig es`\n"
            "Common languages: en, es, fr, de, it, pt, ru, zh, ja, ko",
            parse_mode='Markdown'
        )
        return
    
    try:
        language = event.text.split()[1:][0]
        
        chat_id = str(event.chat_id)
        config = load_config()
        
        if "stt_config" not in config:
            config["stt_config"] = {}
        
        if chat_id not in config["stt_config"]:
            config["stt_config"][chat_id] = {"enabled": False}
        
        config["stt_config"][chat_id]["language"] = language
        save_config(config)
        
        await event.reply(
            f"✅ STT language set to: **{language}**",
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error configuring STT: {e}")
        await event.reply("Error updating STT configuration.")

async def sttstatus(event) -> None:
    """Check STT status for this chat."""
    if not update.message: return
    
    chat_id = str(event.chat_id)
    config = load_config()
    stt_config = config.get("stt_config", {}).get(chat_id, {})
    
    enabled = stt_config.get("enabled", False)
    language = stt_config.get("language", "en")
    
    status = "🎤 **Enabled**" if enabled else "🔇 **Disabled**"
    model_status = "✅ Loaded" if whisper_model else "⏳ Not loaded"
    
    await event.reply(
        f"STT Status: {status}\n"
        f"Language: {language}\n"
        f"Whisper Model ({WHISPER_MODEL_SIZE}): {model_status}",
        parse_mode='Markdown'
    )

# --- Application Lifecycle Hooks ---

async def post_init() -> None:
    """Initialize services after application startup."""
    try:
        logger.info("🚀 Initializing call framework...")
        
        # Initialize Whisper model if configured
        if WHISPER_MODEL_SIZE:
            logger.info("Loading Whisper model for STT...")
            asyncio.create_task(initialize_whisper_model())
        
        # Initialize Telethon client if API credentials are available
        if API_ID and API_HASH:
            logger.info("Initializing Telethon client for pytgcalls...")
            client = await initialize_telethon_client()
            if client:
                logger.info("✅ Telethon client ready")
            else:
                logger.warning("⚠️ Telethon client initialization failed - call features disabled")
        else:
            logger.warning("⚠️ API_ID and API_HASH not set - call features disabled")
        
        logger.info("✅ Call framework initialization complete")
    
    except Exception as e:
        logger.error(f"Error during post_init: {e}", exc_info=True)

async def post_shutdown() -> None:
    """Clean up resources on shutdown."""
    try:
        logger.info("🛑 Shutting down call framework...")
        
        # Leave all active calls
        for chat_id in list(active_calls.keys()):
            try:
                await leave_voice_chat(int(chat_id))
            except Exception as e:
                logger.error(f"Error leaving call in chat {chat_id}: {e}")
        
        # Shutdown Telethon client
        await shutdown_telethon_client()
        
        logger.info("✅ Call framework shutdown complete")
    
    except Exception as e:
        logger.error(f"Error during post_shutdown: {e}", exc_info=True)

# --- Main Function (Telethon) ---
async def async_main():
    """Async main function using Telethon userbot"""
    global global_context, telethon_client, userbot_instance
    
    # Ensure necessary files exist
    if not os.path.exists(CONFIG_FILE): save_config({})
    if not os.path.exists(MEMORY_FILE): save_memory({})
    if not os.path.exists(GOSSIP_FILE): save_gossip({})
    
    # Load config for session settings
    config = load_config()
    session_path = config.get("session_path", "userbot_session")
    use_string_session = config.get("use_string_session", False)
    
    try:
        # Initialize Telethon userbot client
        logger.info("🚀 Initializing Telethon userbot...")
        userbot_instance = create_userbot_from_env(
            session_path=session_path,
            use_string_session=use_string_session
        )
        
        # Start userbot and handle authentication
        client = await userbot_instance.start()
        
        # Initialize context
        global_context = BotContext(client)
        await global_context.initialize()
        telethon_client = client
        
        logger.info("✅ Userbot started successfully")
        
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("Please check your API_ID, API_HASH, and PHONE_NUMBER in .env file")
        raise
    except RuntimeError as e:
        logger.error(f"❌ Connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during startup: {e}", exc_info=True)
        raise
    
    # Schedule daily reminder
    config = load_config()
    reminder_time_str = config.get("reminder_time", "04:00")
    try:
        hour, minute = map(int, reminder_time_str.split(':'))
        reminder_time = time(hour=hour, minute=minute, tzinfo=pytz.timezone('Asia/Kolkata'))
        if not global_context.job_queue.get_jobs_by_name("daily_reminder"):
            global_context.job_queue.run_daily(send_daily_reminder, time=reminder_time, name="daily_reminder")
            logger.info(f"Daily reminder scheduled for {reminder_time_str} IST")
    except Exception as e:
        logger.error(f"Error scheduling daily reminder: {e}")
    
    # Register command handlers
    # Commands are registered via @client.on decorators - see handler definitions
    

    # ========== REGISTER EVENT HANDLERS ==========
    
    # Command Handlers
    @client.on(events.NewMessage(pattern='/start'))
    async def cmd_start(event): await help_command(event)
    
    @client.on(events.NewMessage(pattern='/help'))
    async def cmd_help(event): await help_command(event)
    
    @client.on(events.NewMessage(pattern='/ai'))
    async def cmd_ai(event): await smart_ai_handler(event)
    
    @client.on(events.NewMessage(pattern='/react'))
    async def cmd_react(event): await force_react_command(event)
    
    @client.on(events.NewMessage(pattern='/audio'))
    async def cmd_audio(event): await toggle_audio_mode_handler(event)
    
    @client.on(events.NewMessage(pattern='/chem'))
    async def cmd_chem(event): await chem_handler(event)
    
    @client.on(events.NewMessage(pattern='/tex'))
    async def cmd_tex(event): await latex_handler(event)
    
    @client.on(events.NewMessage(pattern='/chatid'))
    async def cmd_chatid(event): await get_chat_id(event)
    
    @client.on(events.NewMessage(pattern='/summarize'))
    async def cmd_summarize(event): await summarize_command(event)
    
    @client.on(events.NewMessage(pattern='/studypoll'))
    async def cmd_studypoll(event): await studypoll_command(event)
    
    @client.on(events.NewMessage(pattern='/remember'))
    async def cmd_remember(event): await remember_command(event)
    
    @client.on(events.NewMessage(pattern='/recall'))
    async def cmd_recall(event): await recall_command(event)
    
    @client.on(events.NewMessage(pattern='/forget'))
    async def cmd_forget(event): await forget_command(event)
    
    @client.on(events.NewMessage(pattern='/nanoedit'))
    async def cmd_nanoedit(event): await nanoedit_handler(event)
    
    @client.on(events.NewMessage(pattern='/askit'))
    async def cmd_askit(event): await askit_handler(event)
    
    @client.on(events.NewMessage(pattern='/videoedit'))
    async def cmd_videoedit(event): await videoedit_handler(event)
    
    @client.on(events.NewMessage(pattern='/boton'))
    async def cmd_boton(event): await turn_ai_on(event)
    
    @client.on(events.NewMessage(pattern='/botoff'))
    async def cmd_botoff(event): await turn_ai_off(event)
    
    @client.on(events.NewMessage(pattern='/aistatus'))
    async def cmd_aistatus(event): await check_ai_status(event)
    
    @client.on(events.NewMessage(pattern='/randomon'))
    async def cmd_randomon(event): await turn_random_chat_on(event)
    
    @client.on(events.NewMessage(pattern='/randomoff'))
    async def cmd_randomoff(event): await turn_random_chat_off(event)
    
    @client.on(events.NewMessage(pattern='/randomstatus'))
    async def cmd_randomstatus(event): await check_random_status(event)
    
    @client.on(events.NewMessage(pattern='/testrandom'))
    async def cmd_testrandom(event): await test_random_handler(event)
    
    @client.on(events.NewMessage(pattern='/on'))
    async def cmd_modon(event): await turn_moderation_on(event)
    
    @client.on(events.NewMessage(pattern='/off'))
    async def cmd_modoff(event): await turn_moderation_off(event)
    
    @client.on(events.NewMessage(pattern='/time'))
    async def cmd_time(event): await set_reminder_time_handler(event)
    
    @client.on(events.NewMessage(pattern='/callon'))
    async def cmd_callon(event): await turn_proactive_calls_on(event)
    
    @client.on(events.NewMessage(pattern='/calloff'))
    async def cmd_calloff(event): await turn_proactive_calls_off(event)
    
    @client.on(events.NewMessage(pattern='/callstatus'))
    async def cmd_callstatus(event): await check_proactive_calls_status(event)
    
    @client.on(events.NewMessage(pattern='/callquiet'))
    async def cmd_callquiet(event): await set_call_quiet_hours(event)
    
    @client.on(events.NewMessage(pattern='/callconfig'))
    async def cmd_callconfig(event): await configure_call_settings(event)
    
    @client.on(events.NewMessage(pattern='/joincall'))
    async def cmd_joincall(event): await joincall_command(event)
    
    @client.on(events.NewMessage(pattern='/leavecall'))
    async def cmd_leavecall(event): await leavecall_command(event)
    
    @client.on(events.NewMessage(pattern='/callinfo'))
    async def cmd_callinfo(event): await callinfo_command(event)
    
    @client.on(events.NewMessage(pattern='/ttson'))
    async def cmd_ttson(event): await ttson(event)
    
    @client.on(events.NewMessage(pattern='/ttsoff'))
    async def cmd_ttsoff(event): await ttsoff(event)
    
    @client.on(events.NewMessage(pattern='/ttsconfig'))
    async def cmd_ttsconfig(event): await ttsconfig(event)
    
    @client.on(events.NewMessage(pattern='/ttsstatus'))
    async def cmd_ttsstatus(event): await ttsstatus(event)
    
    @client.on(events.NewMessage(pattern='/stton'))
    async def cmd_stton(event): await stton(event)
    
    @client.on(events.NewMessage(pattern='/sttoff'))
    async def cmd_sttoff(event): await sttoff(event)
    
    @client.on(events.NewMessage(pattern='/sttconfig'))
    async def cmd_sttconfig(event): await sttconfig(event)
    
    @client.on(events.NewMessage(pattern='/sttstatus'))
    async def cmd_sttstatus(event): await sttstatus(event)
    
    @client.on(events.NewMessage(pattern='/ban'))
    async def cmd_ban(event): await ban_user(event)
    
    @client.on(events.NewMessage(pattern='/mute'))
    async def cmd_mute(event): await mute_user(event)
    
    @client.on(events.NewMessage(pattern='/unmute'))
    async def cmd_unmute(event): await unmute_user(event)
    
    @client.on(events.NewMessage(pattern='/delete'))
    async def cmd_delete(event): await delete_message(event)
    
    @client.on(events.NewMessage(pattern='/lock'))
    async def cmd_lock(event): await lock_chat(event)
    
    @client.on(events.NewMessage(pattern='/unlock'))
    async def cmd_unlock(event): await unlock_chat(event)
    
    @client.on(events.NewMessage(pattern='/ai1|/ai618'))
    async def cmd_simple_ai(event): await simple_ai_handler(event)
    
    # Voice message handler
    @client.on(events.NewMessage())
    async def voice_handler(event):
        if event.voice:
            await handle_call_audio(event)
    
    # Master text handler for all non-command text
    @client.on(events.NewMessage())
    async def text_handler(event):
        if event.text and not event.text.startswith('/'):
            await master_text_handler(event)
    
    # Poll answer handler
    @client.on(events.Raw)
    async def poll_handler(event):
        if isinstance(event, types.UpdateMessagePollVote):
            # Convert to our expected format
            answer_event = type('PollAnswer', (), {
                'poll_id': event.poll_id,
                'user': await client.get_entity(event.user_id),
                'option_ids': event.options
            })()
            await poll_answer_handler(answer_event)
    
    logger.info("✅ All event handlers registered")
    
    logger.info("🤖 Userbot is running and connected...")
    logger.info("Press Ctrl+C to stop")
    
    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Received shutdown signal...")
    finally:
        # Graceful shutdown
        logger.info("Shutting down userbot...")
        if userbot_instance:
            await userbot_instance.disconnect()
        logger.info("✅ Shutdown complete")

def main():
    """Entry point"""
    asyncio.run(async_main())

if __name__ == '__main__':
    main()
