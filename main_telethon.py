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
from typing import Optional, Tuple, Callable, Any

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
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantsRequest
from telethon.tl.types import ChatBannedRights, ChannelParticipantsAdmins, InputPeerChannel, InputPeerChat, InputMessagesFilterVoice
from telethon.tl.functions.messages import SendReactionRequest

from flask import Flask # Needed for keep_alive

# --- TTS/STT Imports ---
import edge_tts
from faster_whisper import WhisperModel
import soundfile as sf
import numpy as np
import tempfile
import subprocess
from pathlib import Path

# --- pytgcalls Imports (v2.2.8 API) ---
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

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

# --- TTS/STT Configuration ---
API_ID = os.environ.get('API_ID')  # Telegram API ID for Telethon
API_HASH = os.environ.get('API_HASH')  # Telegram API Hash for Telethon
WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')  # tiny, base, small, medium, large
EDGE_TTS_VOICE = os.environ.get('EDGE_TTS_VOICE', 'en-US-AriaNeural')  # Default voice
EDGE_TTS_RATE = os.environ.get('EDGE_TTS_RATE', '+0%')  # Speech rate adjustment
FFMPEG_PATH = os.environ.get('FFMPEG_PATH', 'ffmpeg')  # FFmpeg binary path

# Exit if essential token is missing
if not BOT_TOKEN:
    print("FATAL ERROR: BOT_TOKEN environment variable not set!")
    exit()
if not API_ID or not API_HASH:
    print("FATAL ERROR: API_ID and API_HASH environment variables not set!")
    exit()
if REPLICATE_API_KEY:
    os.environ['REPLICATE_API_TOKEN'] = REPLICATE_API_KEY
else:
    print("WARNING: REPLICATE_API_KEY not set. Audio mode will fail.")

# --- State Management ---
chat_histories = {}
active_random_jobs = set()
trivia_sessions = {}
active_calls = {}
audio_buffers = {}
tts_queues = {}

# --- Global TTS/STT Services ---
whisper_model: Optional[WhisperModel] = None
telethon_client: Optional[TelegramClient] = None
pytgcalls_instances = {}

# --- Job Queue State ---
scheduled_jobs = {}  # {job_name: asyncio.Task}

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


# ==================== CONTEXT WRAPPER ====================
# This wrapper provides a python-telegram-bot-like interface using Telethon

class BotContext:
    """Context wrapper to provide bot functionality similar to python-telegram-bot"""
    
    def __init__(self, client: TelegramClient):
        self.client = client
        self.bot = BotAPI(client)
        self.job_queue = JobQueue(client)
        self.id = None  # Will be set after client starts
    
    async def initialize(self):
        """Initialize the bot context"""
        me = await self.client.get_me()
        self.id = me.id
        self.bot.id = me.id

class BotAPI:
    """Bot API wrapper to mimic python-telegram-bot's bot API"""
    
    def __init__(self, client: TelegramClient):
        self.client = client
        self.id = None
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = None, reply_to_message_id: int = None):
        """Send a text message"""
        try:
            if parse_mode == 'Markdown':
                return await self.client.send_message(chat_id, text, parse_mode='md', reply_to=reply_to_message_id)
            elif parse_mode == 'HTML':
                return await self.client.send_message(chat_id, text, parse_mode='html', reply_to=reply_to_message_id)
            else:
                return await self.client.send_message(chat_id, text, reply_to=reply_to_message_id)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def send_photo(self, chat_id: int, photo, caption: str = None, parse_mode: str = None, reply_to_message_id: int = None):
        """Send a photo"""
        try:
            if parse_mode == 'Markdown':
                return await self.client.send_file(chat_id, photo, caption=caption, parse_mode='md', reply_to=reply_to_message_id)
            elif parse_mode == 'HTML':
                return await self.client.send_file(chat_id, photo, caption=caption, parse_mode='html', reply_to=reply_to_message_id)
            else:
                return await self.client.send_file(chat_id, photo, caption=caption, reply_to=reply_to_message_id)
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            raise
    
    async def send_voice(self, chat_id: int, voice, caption: str = None, reply_to_message_id: int = None):
        """Send a voice message"""
        try:
            return await self.client.send_file(chat_id, voice, voice_note=True, caption=caption, reply_to=reply_to_message_id)
        except Exception as e:
            logger.error(f"Failed to send voice: {e}")
            raise
    
    async def send_video(self, chat_id: int, video, caption: str = None, parse_mode: str = None, reply_to_message_id: int = None, read_timeout=None, write_timeout=None, connect_timeout=None):
        """Send a video"""
        try:
            if parse_mode == 'Markdown':
                return await self.client.send_file(chat_id, video, caption=caption, parse_mode='md', reply_to=reply_to_message_id)
            else:
                return await self.client.send_file(chat_id, video, caption=caption, reply_to=reply_to_message_id)
        except Exception as e:
            logger.error(f"Failed to send video: {e}")
            raise
    
    async def send_sticker(self, chat_id: int, sticker):
        """Send a sticker"""
        try:
            return await self.client.send_file(chat_id, sticker)
        except Exception as e:
            logger.error(f"Failed to send sticker: {e}")
            raise
    
    async def send_poll(self, chat_id: int, question: str, options: list, type: str = 'quiz', correct_option_id: int = None, is_anonymous: bool = False, open_period: int = None):
        """Send a poll"""
        try:
            quiz = (type == 'quiz')
            result = await self.client.send_message(
                chat_id,
                question,
                poll=types.InputMediaPoll(
                    poll=types.Poll(
                        id=0,
                        question=question,
                        answers=[types.PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(options)],
                        closed=False,
                        public_voters=not is_anonymous,
                        quiz=quiz,
                        close_period=open_period,
                        close_date=None
                    ),
                    correct_answers=[bytes([correct_option_id])] if quiz and correct_option_id is not None else None,
                    solution=None
                )
            )
            return result
        except Exception as e:
            logger.error(f"Failed to send poll: {e}")
            raise
    
    async def edit_message_text(self, text: str, chat_id: int, message_id: int, parse_mode: str = None):
        """Edit a message"""
        try:
            if parse_mode == 'Markdown':
                return await self.client.edit_message(chat_id, message_id, text, parse_mode='md')
            elif parse_mode == 'HTML':
                return await self.client.edit_message(chat_id, message_id, text, parse_mode='html')
            else:
                return await self.client.edit_message(chat_id, message_id, text)
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            raise
    
    async def delete_message(self, chat_id: int, message_id: int):
        """Delete a message"""
        try:
            return await self.client.delete_messages(chat_id, [message_id])
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            raise
    
    async def get_chat_administrators(self, chat_id: int):
        """Get chat administrators"""
        try:
            participants = await self.client.get_participants(chat_id, filter=ChannelParticipantsAdmins)
            return participants
        except Exception as e:
            logger.error(f"Failed to get chat administrators: {e}")
            return []
    
    async def set_message_reaction(self, chat_id: int, message_id: int, reaction: list):
        """Set message reaction"""
        try:
            # Telethon reaction API
            emoji_reaction = reaction[0].emoji if hasattr(reaction[0], 'emoji') else reaction[0]
            await self.client(SendReactionRequest(
                peer=chat_id,
                msg_id=message_id,
                reaction=[types.ReactionEmoji(emoticon=emoji_reaction)]
            ))
        except Exception as e:
            logger.error(f"Failed to set reaction: {e}")
            raise
    
    async def ban_chat_member(self, chat_id: int, user_id: int):
        """Ban a user"""
        try:
            await self.client(EditBannedRequest(
                channel=chat_id,
                participant=user_id,
                banned_rights=ChatBannedRights(
                    until_date=None,  # Permanent
                    view_messages=True
                )
            ))
        except Exception as e:
            logger.error(f"Failed to ban user: {e}")
            raise
    
    async def restrict_chat_member(self, chat_id: int, user_id: int, permissions):
        """Restrict a user"""
        try:
            # Convert permissions to ChatBannedRights
            await self.client(EditBannedRequest(
                channel=chat_id,
                participant=user_id,
                banned_rights=ChatBannedRights(
                    until_date=None,
                    send_messages=not getattr(permissions, 'can_send_messages', True),
                    send_media=not getattr(permissions, 'can_send_media_messages', True),
                    send_stickers=not getattr(permissions, 'can_send_other_messages', True),
                    send_gifs=not getattr(permissions, 'can_send_other_messages', True),
                    send_games=not getattr(permissions, 'can_send_other_messages', True),
                    send_inline=not getattr(permissions, 'can_send_other_messages', True),
                    embed_links=not getattr(permissions, 'can_add_web_page_previews', True),
                    send_polls=not getattr(permissions, 'can_send_polls', True),
                    invite_users=not getattr(permissions, 'can_invite_users', True)
                )
            ))
        except Exception as e:
            logger.error(f"Failed to restrict user: {e}")
            raise
    
    async def set_chat_permissions(self, chat_id: int, permissions):
        """Set chat permissions"""
        try:
            # Set default permissions for all users
            await self.client.edit_permissions(
                chat_id,
                send_messages=getattr(permissions, 'can_send_messages', True),
                send_media=getattr(permissions, 'can_send_media_messages', True),
                send_stickers=getattr(permissions, 'can_send_other_messages', True),
                send_gifs=getattr(permissions, 'can_send_other_messages', True),
                send_polls=getattr(permissions, 'can_send_polls', True),
                send_inline=getattr(permissions, 'can_send_other_messages', True),
                embed_links=getattr(permissions, 'can_add_web_page_previews', True),
                invite_users=getattr(permissions, 'can_invite_users', True)
            )
        except Exception as e:
            logger.error(f"Failed to set chat permissions: {e}")
            raise

class JobQueue:
    """Job queue wrapper to schedule tasks"""
    
    def __init__(self, client: TelegramClient):
        self.client = client
        self.jobs = {}
    
    def run_once(self, callback: Callable, when: float, data: dict = None, name: str = None):
        """Schedule a one-time job"""
        async def job_wrapper():
            await asyncio.sleep(when)
            # Create a context-like object
            job_data = type('JobData', (), {'data': data, 'name': name})()
            context_obj = type('Context', (), {'job': job_data, 'bot': BotContext.instance.bot})()
            await callback(context_obj)
            if name and name in self.jobs:
                del self.jobs[name]
        
        task = asyncio.create_task(job_wrapper())
        if name:
            self.jobs[name] = task
        return task
    
    def run_daily(self, callback: Callable, time: time, data: dict = None, name: str = None):
        """Schedule a daily recurring job"""
        async def daily_job_wrapper():
            while True:
                now = datetime.now(time.tzinfo)
                target = now.replace(hour=time.hour, minute=time.minute, second=time.second, microsecond=0)
                if target <= now:
                    target = target.replace(day=target.day + 1)
                delay = (target - now).total_seconds()
                await asyncio.sleep(delay)
                
                # Create a context-like object
                job_data = type('JobData', (), {'data': data, 'name': name})()
                context_obj = type('Context', (), {'job': job_data, 'bot': BotContext.instance.bot})()
                await callback(context_obj)
        
        task = asyncio.create_task(daily_job_wrapper())
        if name:
            self.jobs[name] = task
        return task
    
    def get_jobs_by_name(self, name: str):
        """Get jobs by name"""
        return [self.jobs[name]] if name in self.jobs else []

# Global context instance
BotContext.instance = None

class ChatPermissions:
    """Chat permissions class to mimic python-telegram-bot"""
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
    """Reaction type emoji class"""
    def __init__(self, emoji: str):
        self.emoji = emoji

# ==================== END CONTEXT WRAPPER ====================
