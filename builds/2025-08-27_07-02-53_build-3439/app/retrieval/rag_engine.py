import logging
import time
from typing import Dict, List, Any, Optional
import openai
import os
from app.common.astra_client import get_vector_store
from app.common.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

class RAGEngine:
    """Retrieval-Augmented Generation engine for TTRPG queries"""
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.embedding_service = get_embedding_service()
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def query(self, 
              query: str,
              filters: Optional[Dict[str, Any]] = None,
              k: int = 6,
              rerank: bool = True) -> Dict[str, Any]:
        """
        Execute RAG query and return response with sources
        """
        start_time = time.time()
        
        logger.info(f"RAG query: {query[:50]}...")
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.get_embedding(query)
            if not query_embedding:
                return self._fallback_response(query, "Failed to generate query embedding")
            
            # Perform vector search
            search_results = self.vector_store.similarity_search(
                query_embedding=query_embedding,
                k=k * 2 if rerank else k,  # Get more for reranking
                filters=filters
            )
            
            if not search_results:
                return self._fallback_response(query, "No relevant information found in knowledge base")
            
            # Rerank results if requested
            if rerank and len(search_results) > k:
                search_results = self._rerank_results(query, search_results)[:k]
            
            # Generate response with RAG context
            response_text = self._generate_rag_response(query, search_results)
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "response": response_text,
                "sources": self._format_sources(search_results),
                "retrieval_results": len(search_results),
                "latency_ms": latency_ms,
                "query_type": "rag_lookup",
                "model": "openai:gpt-4o-mini",
                "tokens": self._estimate_tokens(query, response_text, search_results),
                "success": True
            }
            
            logger.info(f"RAG response generated in {latency_ms}ms with {len(search_results)} sources")
            return result
            
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {
                "response": f"I encountered an error while searching for information: {str(e)}",
                "sources": [],
                "success": False,
                "error": str(e),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
    
    def _rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rerank search results using additional scoring"""
        try:
            # Simple reranking based on text similarity and metadata
            scored_results = []
            
            query_words = set(query.lower().split())
            
            for result in results:
                score = result["score"]  # Original vector similarity
                text_words = set(result["text"].lower().split())
                
                # Boost score for exact word matches
                word_overlap = len(query_words.intersection(text_words))
                word_boost = word_overlap / len(query_words) * 0.1
                
                # Boost for certain metadata
                metadata_boost = 0.0
                if result.get("metadata", {}).get("section", "").lower() in query.lower():
                    metadata_boost += 0.05
                
                # Penalize very short chunks
                if len(result["text"]) < 100:
                    metadata_boost -= 0.05
                
                final_score = score + word_boost + metadata_boost
                
                scored_results.append({
                    **result,
                    "rerank_score": final_score
                })
            
            # Sort by reranked score
            return sorted(scored_results, key=lambda x: x["rerank_score"], reverse=True)
            
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using original order")
            return results
    
    def _generate_rag_response(self, query: str, sources: List[Dict[str, Any]]) -> str:
        """Generate response using retrieved sources"""
        try:
            # Build context from sources
            context_parts = []
            for i, source in enumerate(sources[:4], 1):  # Limit to top 4 sources
                source_text = source["text"][:400]  # Truncate long sources
                source_info = f"Source {i} (from {source['source_id']}, page {source['page']}): {source_text}"
                context_parts.append(source_info)
            
            context = "\n\n".join(context_parts)
            
            # Build system prompt
            system_prompt = """You are a knowledgeable TTRPG assistant. Answer the user's question using the provided source information. 

Guidelines:
- Be accurate and cite specific sources when possible
- If sources don't fully answer the question, say so clearly
- Use the exact terminology from the sources
- Be helpful and provide context when appropriate
- If multiple sources conflict, mention the discrepancy
- Keep responses concise but complete"""
            
            # Build user prompt
            user_prompt = f"""Question: {query}

Source Information:
{context}

Please answer the question based on the provided sources."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=600
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"RAG response generation failed: {e}")
            return f"I found relevant information but had trouble generating a response. The sources mention: {sources[0]['text'][:200] if sources else 'No sources available'}"
    
    def _fallback_response(self, query: str, reason: str) -> Dict[str, Any]:
        """Generate fallback response using OpenAI training data"""
        try:
            logger.info(f"Using fallback for query: {reason}")
            
            system_prompt = """You are a knowledgeable TTRPG assistant. The user is asking about tabletop RPG topics. 

Since I don't have specific source materials available for this query, I'll provide general information based on common TTRPG knowledge. Please note that you should verify specific rules with official source books.

Be helpful but clearly indicate this is general guidance."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.3,
                max_tokens=400
            )
            
            fallback_text = response.choices[0].message.content.strip()
            fallback_text += "\n\n*Note: This response is based on general TTRPG knowledge. Please verify with official source materials.*"
            
            return {
                "response": fallback_text,
                "sources": [],
                "query_type": "fallback",
                "model": "openai:gpt-4o-mini",
                "success": True,
                "fallback_reason": reason
            }
            
        except Exception as e:
            logger.error(f"Fallback response failed: {e}")
            return {
                "response": "I apologize, but I'm having trouble answering your question right now. Please try rephrasing or ask about something more specific.",
                "sources": [],
                "success": False,
                "error": str(e)
            }
    
    def _format_sources(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source information for response"""
        sources = []
        for result in results:
            sources.append({
                "source_id": result["source_id"],
                "page": result["page"],
                "section": result.get("section", ""),
                "score": round(result["score"], 3),
                "text_preview": result["text"][:150] + "..." if len(result["text"]) > 150 else result["text"]
            })
        return sources
    
    def _estimate_tokens(self, query: str, response: str, sources: List[Dict[str, Any]]) -> Dict[str, int]:
        """Estimate token usage for the RAG query"""
        # Rough estimation: 1 token ≈ 0.75 words
        query_tokens = int(len(query.split()) * 1.33)
        response_tokens = int(len(response.split()) * 1.33)
        
        # Context tokens from sources
        context_text = " ".join([s["text"][:400] for s in sources[:4]])
        context_tokens = int(len(context_text.split()) * 1.33)
        
        # Add system prompt overhead
        system_overhead = 100
        
        return {
            "prompt": query_tokens + context_tokens + system_overhead,
            "completion": response_tokens,
            "total": query_tokens + context_tokens + system_overhead + response_tokens
        }

# Global instance
_rag_engine = None

def get_rag_engine() -> RAGEngine:
    """Get global RAG engine instance"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine