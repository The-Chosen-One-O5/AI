import logging
import os
import asyncio
import json
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

    # 5. "Should I Speak?" Logic
    should_reply = False
    is_mention = f"@{context.bot.username}" in text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id)
    
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

    # 6. Generate Response
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
            await update.message.reply_text(response)

    # 7. Learn Facts
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

    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start_command))
    
    # Tools
    app.add_handler(CommandHandler("chem", tools.handle_chemistry))
    app.add_handler(CommandHandler("tex", tools.handle_latex))
    
    # Features & Memory
    app.add_handler(CommandHandler("forget", lambda u, c: memory_manager.forget_user(u.effective_user.id)))
    app.add_handler(CommandHandler("random", feature_manager.toggle_random))
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
    import random # Needed for the random timer
    main()
