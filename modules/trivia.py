import logging
import json
import re
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class TriviaManager:
    def __init__(self, api_client):
        self.sessions = {} # {chat_id: session_data}
        self.api_client = api_client

    async def start_trivia(self, update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str, q_count: int):
        chat_id = str(update.effective_chat.id)
        if self.sessions.get(chat_id, {}).get("state") in ["registering", "asking"]:
            await update.message.reply_text("A game is already in progress!")
            return

        intro = await update.message.reply_text(
            f"🔥 **TRIVIA TIME!** 🔥\nTopic: {topic}\nRounds: {q_count}\n\nReply `me` to join!\nReply `all in` to start!",
            parse_mode='Markdown'
        )
        
        self.sessions[chat_id] = {
            "state": "registering",
            "topic": topic,
            "total_questions": q_count,
            "current_question": 0,
            "players": {},
            "reg_msg_id": intro.message_id,
            "asked": []
        }

    async def handle_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        chat_id = str(update.effective_chat.id)
        session = self.sessions.get(chat_id)
        if not session or session["state"] != "registering":
            return False

        text = update.message.text.lower().strip()
        user = update.message.from_user

        # Verify reply to bot's intro message
        if update.message.reply_to_message and update.message.reply_to_message.message_id == session["reg_msg_id"]:
            if text == "me":
                if user.id not in session["players"]:
                    session["players"][user.id] = {"name": user.first_name, "score": 0}
                    await update.message.reply_text(f"{user.first_name} joined! ✅")
                return True
            
            elif text == "all in":
                if not session["players"]:
                    await update.message.reply_text("Need at least 1 player!")
                    return True
                await update.message.reply_text("Registration Closed! Starting...")
                session["state"] = "asking"
                await self.ask_question(context, chat_id)
                return True
        
        return False

    async def ask_question(self, context: ContextTypes.DEFAULT_TYPE, chat_id: str):
        session = self.sessions.get(chat_id)
        if not session or session["current_question"] >= session["total_questions"]:
            await self.end_game(context, chat_id)
            return

        session["current_question"] += 1
        
        # Get question from AI
        prompt = [
            {"role": "system", "content": "You are a trivia host. Generate JSON."},
            {"role": "user", "content": f"Generate 1 hard multiple choice question about {session['topic']}. "
                                      f"Format: JSON with keys 'question', 'options' (list of 4), 'correct_index' (0-3). "
                                      f"Avoid these previous questions: {session['asked']}"}
        ]
        
        resp = await self.api_client.get_text_response(prompt)
        # Simple parsing (in production, add robust JSON extraction)
        try:
            data = json.loads(re.search(r'\{.*\}', resp, re.DOTALL).group())
            session["current_correct"] = data['correct_index']
            session["asked"].append(data['question'])
            
            message = await context.bot.send_poll(
                chat_id=int(chat_id),
                question=f"Q{session['current_question']}: {data['question']}",
                options=data['options'],
                type='quiz',
                correct_option_id=data['correct_index'],
                open_period=30,
                is_anonymous=False
            )
            session["poll_id"] = message.poll.id
        except Exception as e:
            logger.error(f"Trivia error: {e}")
            await context.bot.send_message(int(chat_id), "Error generating question. Skipping...")
            await self.ask_question(context, chat_id)

    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Logic to update scores based on poll answers
        # Note: Telegram Poll API handles correctness, we just track score
        answer = update.poll_answer
        # Find session by poll_id implies searching all sessions (simplified here)
        # For production, map poll_id -> chat_id
        pass 

    async def end_game(self, context, chat_id):
        session = self.sessions.get(chat_id)
        if not session: return
        
        scores = sorted(session["players"].items(), key=lambda x: x[1]['score'], reverse=True)
        text = "🏆 **FINAL SCORES** 🏆\n\n" + "\n".join([f"{p['name']}: {p['score']}" for _, p in scores])
        await context.bot.send_message(int(chat_id), text, parse_mode='Markdown')
        del self.sessions[chat_id]
