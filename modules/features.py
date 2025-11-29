import random
import logging
import asyncio
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class FeatureManager:
    def __init__(self, api_client):
        self.api_client = api_client
        self.random_chat_enabled = True
        self.speak_mode_enabled = {}  # Per-user/chat speak mode state

    async def random_chat_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Background job to send a random message."""
        chat_id = context.job.data['chat_id']
        history = context.job.data.get('history', [])
        
        if not history or not self.random_chat_enabled:
            return

        # Construct a "lurker" prompt
        prompt = [
            {"role": "system", "content": "You are a witty group chat member. Read the chat log and make ONE short, funny, or provocative comment. Don't be helpful. Be casual."},
            {"role": "user", "content": f"Chat Log:\n{history}\n\nYour Comment:"}
        ]
        
        response = await self.api_client.get_text_response(prompt)
        if response:
            await context.bot.send_message(chat_id=chat_id, text=response)

    async def handle_reaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Randomly reacts to messages with emojis."""
        if not update.message or not update.message.text:
            return
            
        # 10% chance to react naturally
        if random.random() > 0.1:
            return

        prompt = [
            {"role": "system", "content": "You are an emoji bot. Respond with ONLY ONE emoji that fits the message."},
            {"role": "user", "content": update.message.text}
        ]
        
        emoji = await self.api_client.get_text_response(prompt)
        
        # Basic validation to ensure it's an emoji (simple check)
        if emoji and len(emoji) < 4: 
            try:
                await update.message.set_reaction(reaction=[ReactionTypeEmoji(emoji.strip())])
            except Exception as e:
                logger.warning(f"Reaction failed: {e}")

    async def toggle_random(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.random_chat_enabled = not self.random_chat_enabled
        state = "ON" if self.random_chat_enabled else "OFF"
        await update.message.reply_text(f"🎲 Random Chat is now **{state}**.")

    async def toggle_speak(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle speak mode for the user."""
        user_id = update.effective_user.id
        current_state = self.speak_mode_enabled.get(user_id, False)
        new_state = not current_state
        self.speak_mode_enabled[user_id] = new_state
        
        state = "ON" if new_state else "OFF"
        if new_state:
            await update.message.reply_text(f"🎤 Speak Mode is now **{state}**. I will respond with audio messages only.")
        else:
            await update.message.reply_text(f"🎤 Speak Mode is now **{state}**. I will respond with text messages.")
    
    def is_speak_mode_enabled(self, user_id: int) -> bool:
        """Check if speak mode is enabled for a user."""
        return self.speak_mode_enabled.get(user_id, False)
