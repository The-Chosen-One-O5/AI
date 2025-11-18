import logging
import os
import random
import asyncio
import json
from collections import deque
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, PollAnswerHandler, filters, ContextTypes

# --- Internal Modules ---
from keep_alive import keep_alive
from ai.memory_manager import MemoryManager
from ai.decision_logic import DecisionEngine
from ai.api_client import APIClient
from modules.trivia import TriviaManager
from modules import tools

# --- Config ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWNER_ID = os.environ.get('OWNER_ID')

# --- Initialization ---
api_client = APIClient()
memory_manager = MemoryManager(os.environ.get('OPENAI_API_KEY'))
decision_engine = DecisionEngine(bot_name="AI618")
trivia_manager = TriviaManager(api_client)

# Chat History (In-memory for context window)
chat_histories = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I am AI618 (The Chosen One). I have memory and I decide when to speak.")

async def master_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    text = update.message.text
    
    # 1. Handle Trivia Registration (if active)
    if await trivia_manager.handle_registration(update, context):
        return

    # 2. Update History
    if chat_id not in chat_histories: chat_histories[chat_id] = deque(maxlen=15)
    chat_histories[chat_id].append(f"[{user.first_name}]: {text}")

    # 3. Check "Should I Speak?" (The AI Brain)
    # We skip this if it's a direct command, but for general text we check.
    should_reply = False
    
    # Logic: Always reply to mentions/replies
    is_mention = f"@{context.bot.username}" in text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id)
    
    if is_mention:
        should_reply = True
        reason = "Direct mention"
    else:
        # Ask AI decision engine
        decision_prompt = decision_engine.get_decision_prompt(text, list(chat_histories[chat_id]))
        decision_json = await api_client.get_text_response([{"role": "user", "content": decision_prompt}])
        try:
            decision = json.loads(decision_json)
            should_reply = decision.get("should_reply", False)
            reason = decision.get("reason", "AI decided")
        except:
            should_reply = False # Fallback to silence if JSON fails

    # 4. Generate Response
    if should_reply:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Retrieve Memories
        memories = memory_manager.get_relevant_memories(user.id, text)
        
        # Construct Prompt
        system_prompt = decision_engine.get_response_prompt(
            user_name=user.first_name,
            message=text,
            memories=memories,
            history=list(chat_histories[chat_id])
        )
        
        response = await api_client.get_text_response([{"role": "user", "content": system_prompt}])
        
        if response:
            # Check for Audio Mode
            # (Simple check via config dict - you can expand this)
            # if audio_enabled:
            #    audio = await tools.generate_audio(response, "en-US-GuyNeural")
            #    await context.bot.send_voice(chat_id, audio)
            # else:
            await update.message.reply_text(response)

    # 5. Learn Facts (Background Task)
    # Only run for longer messages to save resources
    if len(text.split()) > 4:
        fact_prompt = decision_engine.extract_fact_prompt(user.first_name, text)
        fact = await api_client.get_text_response([{"role": "user", "content": fact_prompt}])
        if fact and "None" not in fact:
            memory_manager.add_memory(user.id, user.first_name, fact)

# --- Commands ---
async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /ai start trivia on Topic 5Q
    args = context.args
    if "start" in args and "trivia" in args:
        topic = "General"
        count = 5
        # Simple parsing logic here...
        await trivia_manager.start_trivia(update, context, topic, count)

async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory_manager.forget_user(update.effective_user.id)
    await update.message.reply_text("I have wiped my memory of you.")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("chem", tools.handle_chemistry))
    app.add_handler(CommandHandler("tex", tools.handle_latex))
    app.add_handler(CommandHandler("forget", forget_command))
    app.add_handler(CommandHandler("ai", trivia_command)) # Example integration
    
    # Trivia Poll Handler
    app.add_handler(PollAnswerHandler(trivia_manager.handle_poll_answer))
    
    # Master Text Handler (The Brain)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, master_text_handler))

    keep_alive()
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
