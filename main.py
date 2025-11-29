import logging
import os
import asyncio
import json
import random
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, PollAnswerHandler, filters, ContextTypes

# --- Internal Modules ---
from keep_alive import keep_alive
from ai.memory_manager import MemoryManager
from ai.decision_logic import DecisionEngine
from ai.api_client import APIClient
from modules.trivia import TriviaManager
from modules import tools
from modules import admin
from modules import media
from modules.features import FeatureManager

# --- Config ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# --- Initialization ---
api_client = APIClient()
memory_manager = MemoryManager(os.environ.get('OPENAI_API_KEY'))
decision_engine = DecisionEngine(bot_name="AI618")
trivia_manager = TriviaManager(api_client)
feature_manager = FeatureManager(api_client)

# Chat History (In-memory for context window)
chat_histories = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I am AI618 (The Chosen One). Ready to serve.")

async def master_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    text = update.message.text
    text_lower = text.lower()
    
    # 1. Update History
    if chat_id not in chat_histories: chat_histories[chat_id] = deque(maxlen=15)
    chat_histories[chat_id].append(f"[{user.first_name}]: {text}")

    # 2. Handle Trivia Registration (if active)
    if await trivia_manager.handle_registration(update, context):
        return

    # 3. Proactive Reactions (The "Vibe" Check)
    await feature_manager.handle_reaction(update, context)

    # 4. Random Chat Scheduling
    # Every message resets the timer for a potential "random" comment from the bot
    # We use `run_once` to debounce it.
    if context.job_queue:  # Only if job_queue is available
        job_name = f"random_chat_{chat_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs: job.schedule_removal() # Cancel previous timer
        
        # Schedule new random chat in 10-30 minutes (simulating a lurker)
        # Only if enabled
        if feature_manager.random_chat_enabled:
            context.job_queue.run_once(
                feature_manager.random_chat_job, 
                when=random.randint(600, 1800), 
                data={'chat_id': chat_id, 'history': list(chat_histories[chat_id])},
                name=job_name
            )

    # 5. Natural Language Feature Triggers
    
    # Image Generation
    if "generate image" in text_lower or "create image" in text_lower:
        prompt = text_lower.replace("generate image", "").replace("create image", "").strip()
        if prompt:
            status_msg = await update.message.reply_text("🎨 Painting your imagination...")
            try:
                image_url = await media.generate_image_url(prompt)
                if image_url:
                    await update.message.reply_photo(photo=image_url, caption=f"🎨 {prompt}")
                    await status_msg.delete()
                else:
                    await status_msg.edit_text("❌ Image generation failed.")
            except Exception as e:
                logger.error(f"Image generation error: {e}")
                await status_msg.edit_text(f"❌ Error: {str(e)}")
            return

    # Video Generation
    if "generate video" in text_lower or "create video" in text_lower:
        prompt = text_lower.replace("generate video", "").replace("create video", "").strip()
        if prompt:
            status_msg = await update.message.reply_text("🎬 Directing scene (this may take a while)...")
            try:
                video_url = await media.generate_video_url(prompt)
                if video_url:
                    await update.message.reply_video(video=video_url, caption=f"🎬 {prompt}")
                    await status_msg.delete()
                else:
                    await status_msg.edit_text("❌ Video generation failed.")
            except Exception as e:
                logger.error(f"Video generation error: {e}")
                await status_msg.edit_text(f"❌ Error: {str(e)}")
            return

    # Vision (Explain this)
    if ("explain this" in text_lower or "what is this" in text_lower) and update.message.reply_to_message and update.message.reply_to_message.photo:
        status_msg = await update.message.reply_text("👀 Analyzing image...")
        try:
            photo = update.message.reply_to_message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_url = file.file_path
            caption = await media.analyze_image_url(image_url)
            if caption:
                await update.message.reply_text(f"👀 I see: {caption}")
                await status_msg.delete()
            else:
                 await status_msg.edit_text("❌ Could not analyze image.")
        except Exception as e:
            logger.error(f"Vision error: {e}")
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        return

    # 6. "Should I Speak?" Logic
    should_reply = False
    is_mention = f"@{context.bot.username}" in text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id)
    
    # Smart Mention: Check for name or "bot"
    if "ai618" in text_lower or "bot" in text_lower:
        is_mention = True

    if is_mention:
        should_reply = True
    else:
        # Ask AI decision engine
        decision_prompt = decision_engine.get_decision_prompt(text, list(chat_histories[chat_id]))
        decision_json = await api_client.get_text_response([{"role": "user", "content": decision_prompt}])
        try:
            decision = json.loads(decision_json)
            should_reply = decision.get("should_reply", False)
        except:
            should_reply = False 

    # 7. Generate Response
    if should_reply:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        memories = memory_manager.get_relevant_memories(user.id, text)
        
        system_prompt = decision_engine.get_response_prompt(
            user_name=user.first_name,
            message=text,
            memories=memories,
            history=list(chat_histories[chat_id])
        )
        
        response = await api_client.get_text_response([{"role": "user", "content": system_prompt}])
        if response:
            if feature_manager.is_speak_mode_enabled(user.id):
                await media.send_audio_response(response, update, context)
            else:
                await update.message.reply_text(response)

    # 8. Learn Facts
    if len(text.split()) > 4:
        fact_prompt = decision_engine.extract_fact_prompt(user.first_name, text)
        fact = await api_client.get_text_response([{"role": "user", "content": fact_prompt}])
        if fact and "None" not in fact:
            memory_manager.add_memory(user.id, user.first_name, fact)

# --- Commands ---
async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await trivia_manager.start_trivia(update, context, "General", 5)

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found.")
        return
    
    if not os.environ.get('OPENAI_API_KEY'):
        print("Warning: OPENAI_API_KEY not found. Memory and some features may not work.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start_command))
    
    # Tools
    app.add_handler(CommandHandler("chem", tools.handle_chemistry))
    app.add_handler(CommandHandler("tex", tools.handle_latex))
    
    # Media (Audio/Visual)
    app.add_handler(CommandHandler("audio", media.handle_audio))
    app.add_handler(CommandHandler("audioselect", media.handle_audioselect))
    app.add_handler(CommandHandler("ttsvoice", media.handle_tts_voice))
    app.add_handler(CommandHandler("image", media.handle_image))
    app.add_handler(CommandHandler("askit", media.handle_askit))
    app.add_handler(CommandHandler("video", media.handle_video))
    
    # Features & Memory
    app.add_handler(CommandHandler("forget", lambda u, c: memory_manager.forget_user(u.effective_user.id)))
    app.add_handler(CommandHandler("random", feature_manager.toggle_random))
    app.add_handler(CommandHandler("speak", feature_manager.toggle_speak))
    app.add_handler(CommandHandler("ai", trivia_command)) # Alias for now
    
    # Admin / Moderation
    app.add_handler(CommandHandler("ban", admin.ban_user))
    app.add_handler(CommandHandler("mute", admin.mute_user))
    app.add_handler(CommandHandler("unmute", admin.unmute_user))
    app.add_handler(CommandHandler("delete", admin.delete_message))

    # Trivia Poll Handler
    app.add_handler(PollAnswerHandler(trivia_manager.handle_poll_answer))
    
    # Master Text Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, master_text_handler))

    keep_alive()
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
