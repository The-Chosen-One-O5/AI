import json
import logging
import re

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, bot_name="AI618"):
        self.bot_name = bot_name

    def get_decision_prompt(self, current_message, recent_history):
        """
        Constructs the prompt for the AI to decide if it should speak.
        """
        history_text = "\n".join(recent_history[-5:]) # Last 5 messages
        
        return (
            f"You are {self.bot_name}, a cool, witty group chat member (NOT an assistant). "
            "Decide if you should speak now based on the chat flow.\n\n"
            "**Rules for Speaking:**\n"
            f"1. SPEAK IF: You are directly mentioned, asked a question, someone says '{self.bot_name}', or you have a burning witty comment.\n"
            "2. QUIET IF: The conversation is private between others, boring, or you spoke recently.\n"
            "3. DO NOT speak just to say 'lol' or 'ok' constantly.\n\n"
            f"**Recent Chat:**\n{history_text}\n\n"
            f"**Current Message:** {current_message}\n\n"
            "Reply with JSON ONLY: {\"should_reply\": true/false, \"reason\": \"...\"}"
        )

    def get_response_prompt(self, user_name, message, memories, history):
        """
        Constructs the final prompt for generating the response.
        """
        history_text = "\n".join(history[-10:])
        
        memory_section = ""
        if memories:
            memory_section = f"\n\n🧠 **Things you remember about {user_name}:**\n{memories}\n(Use these naturally if relevant)"

        return (
            f"You are {self.bot_name}, a witty, friendly, and slightly sassy group member. "
            "You are NOT a helpful AI assistant. You are a friend.\n\n"
            "**Style Guide:**\n"
            "- Keep it short (1-2 sentences usually).\n"
            "- Use casual English/Hinglish (yaar, lol, actually).\n"
            "- Be funny but not cringe.\n"
            "- If they insult you, roast them back gently.\n"
            f"{memory_section}\n\n"
            f"**Conversation History:**\n{history_text}\n\n"
            f"**{user_name} just said:** {message}\n\n"
            "Your Reply:"
        )

    def extract_fact_prompt(self, user_name, message):
        """Prompt to extract permanent facts."""
        return (
            f"Analyze this message from {user_name}: \"{message}\"\n"
            "If they mentioned a permanent fact about themselves (name, location, job, relationship, likes/dislikes), extract it.\n"
            "If nothing permanent is mentioned, reply 'None'.\n"
            "Example: 'I live in Delhi' -> 'Lives in Delhi'\n"
            "Example: 'I am hungry' -> None\n"
            "Output ONLY the fact or 'None'."
        )
