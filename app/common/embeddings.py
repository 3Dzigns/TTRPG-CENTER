import os
import logging
import openai
from typing import List, Dict, Any
import time
import tiktoken

logger = logging.getLogger(__name__)

class EmbeddingService:
    """OpenAI embedding service for text vectorization"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        try:
            # Clean and truncate text if needed
            text = text.replace("\n", " ").strip()
            
            # Check token count (max 8191 for ada-002)
            tokens = self.encoding.encode(text)
            if len(tokens) > 8000:  # Leave some buffer
                # Truncate to fit
                truncated_tokens = tokens[:8000]
                text = self.encoding.decode(truncated_tokens)
                logger.warning(f"Text truncated from {len(tokens)} to {len(truncated_tokens)} tokens")
            
            # Retry logic for transient failures
            for attempt in range(3):
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=text
                    )
                    return response.data[0].embedding
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise
                    logger.warning(f"Embedding attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(0.5 * (attempt + 1))
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Get embeddings for multiple texts in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._get_batch_embeddings(batch)
            embeddings.extend(batch_embeddings)
            
            # Rate limiting
            if i + batch_size < len(texts):
                time.sleep(0.1)
        
        return embeddings
    
    def _get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a single batch"""
        try:
            # Clean texts
            cleaned_texts = []
            for text in texts:
                text = text.replace("\n", " ").strip()
                
                # Check token count
                tokens = self.encoding.encode(text)
                if len(tokens) > 8000:
                    truncated_tokens = tokens[:8000]
                    text = self.encoding.decode(truncated_tokens)
                
                cleaned_texts.append(text)
            
            # Retry logic for batch embeddings
            for attempt in range(3):
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=cleaned_texts
                    )
                    return [item.embedding for item in response.data]
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise
                    logger.warning(f"Batch embedding attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(0.5 * (attempt + 1))
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [[] for _ in texts]

# Global instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service