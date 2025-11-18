import os
import logging
import asyncio
import json
import httpx
from cerebras.cloud.sdk import Cerebras
from groq import AsyncGroq
from openai import OpenAIError

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        # Load keys
        self.cerebras_key = os.environ.get('CEREBRAS_API_KEY')
        self.groq_key = os.environ.get('GROQ_API_KEY')
        self.chatanywhere_key = os.environ.get('CHATANYWHERE_API_KEY')
        self.typegpt_key = os.environ.get('TYPEGPT_FAST_API_KEY')
        self.brave_key = os.environ.get('BRAVE_API_KEY')

    async def get_text_response(self, messages) -> str | None:
        """
        Orchestrates the fallback chain: Cerebras -> Groq -> ChatAnywhere
        """
        logger.info("--- Starting AI Fallback Chain ---")

        # 1. Primary: Cerebras
        if self.cerebras_key:
            response = await self._call_cerebras(messages)
            if response: return response
        
        # 2. Fallback: Groq
        if self.groq_key:
            logger.warning("Cerebras failed. Trying Groq.")
            response = await self._call_groq(messages)
            if response: return response

        # 3. Fallback: ChatAnywhere
        if self.chatanywhere_key:
            logger.warning("Groq failed. Trying ChatAnywhere.")
            response = await self._call_chatanywhere(messages)
            if response: return response

        logger.error("All AI providers failed.")
        return None

    async def _call_cerebras(self, messages):
        try:
            client = Cerebras(api_key=self.cerebras_key)
            # Cerebras SDK is sync, run in thread
            def run_sync():
                return client.chat.completions.create(
                    messages=messages,
                    model="zai-glm-4.6",
                    stream=False
                )
            completion = await asyncio.to_thread(run_sync)
            return completion.choices[0].message.content
        except Exception as e:
            logger.warning(f"Cerebras Error: {e}")
            return None

    async def _call_groq(self, messages):
        try:
            client = AsyncGroq(api_key=self.groq_key)
            completion = await client.chat.completions.create(
                messages=messages,
                model="llama3-70b-8192", # Updated model name
                temperature=0.7
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.warning(f"Groq Error: {e}")
            return None

    async def _call_chatanywhere(self, messages):
        try:
            url = "https://api.chatanywhere.tech/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.chatanywhere_key}"}
            payload = {"model": "gpt-3.5-turbo", "messages": messages}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.warning(f"ChatAnywhere Error: {e}")
            return None

    async def web_search(self, query):
        if not self.brave_key: return "Web search disabled."
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {"X-Subscription-Token": self.brave_key}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, params={"q": query})
                if resp.status_code == 200:
                    results = resp.json().get('web', {}).get('results', [])
                    return "\n".join([f"- {r['title']}: {r['description']}" for r in results[:3]])
        except Exception as e:
            logger.error(f"Search error: {e}")
        return "Search failed."
