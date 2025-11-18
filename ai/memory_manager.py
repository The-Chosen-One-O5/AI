import os
import logging
import hashlib
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, openai_api_key=None):
        # Setup storage path
        self.db_path = "data/memory_db"
        os.makedirs(self.db_path, exist_ok=True)
        
        # Initialize ChromaDB Client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Setup Embeddings: Use OpenAI if available, else default to local (free)
        # This ensures it works even without paid keys
        if openai_api_key:
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai_api_key,
                model_name="text-embedding-3-small"
            )
            logger.info("Memory Manager: Using OpenAI Embeddings")
        else:
            # Default uses all-MiniLM-L6-v2 (runs locally, no API key needed)
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            logger.info("Memory Manager: Using Local Default Embeddings (Free)")
        
        # Get or create the collection for user memories
        self.collection = self.client.get_or_create_collection(
            name="user_personalities",
            embedding_function=self.embedding_fn
        )
        
        logger.info(f"Memory Manager initialized. Collection count: {self.collection.count()}")

    def add_memory(self, user_id: int, username: str, fact: str):
        """Save a new fact about a user."""
        if not fact or len(fact.strip()) < 5:
            return

        try:
            # Create a unique ID for this memory to prevent duplicates
            # Hashing the fact ensures we don't store "I like cats" twice for the same user
            fact_id = f"{user_id}_{hashlib.md5(fact.encode()).hexdigest()}"
            
            # Check if already exists
            existing = self.collection.get(ids=[fact_id])
            if existing and existing['ids']:
                return

            self.collection.add(
                documents=[fact],
                metadatas=[{"user_id": str(user_id), "username": str(username)}],
                ids=[fact_id]
            )
            logger.info(f"🧠 Memory added for {username}: {fact[:30]}...")
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")

    def get_relevant_memories(self, user_id: int, query_text: str, limit: int = 3) -> str:
        """
        Find past memories relevant to the current topic (RAG).
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=limit,
                where={"user_id": str(user_id)}  # Filter by this user
            )
            
            if not results['documents'] or not results['documents'][0]:
                return ""
                
            # Format as a bulleted list
            memories = results['documents'][0]
            formatted = "\n".join([f"- {m}" for m in memories])
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return ""

    def forget_user(self, user_id: int):
        """Delete all memories for a user."""
        try:
            self.collection.delete(where={"user_id": str(user_id)})
            return True
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return False
