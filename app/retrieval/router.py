import logging
import openai
import os
import re
from typing import Dict, List, Any, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class QueryType(Enum):
    RAG_LOOKUP = "rag_lookup"          # Factual queries, rules lookup, lists
    WORKFLOW = "workflow"              # Multi-step tasks like character creation
    CALCULATION = "calculation"        # Math, dice rolls, stat calculations
    FALLBACK = "fallback"             # Use OpenAI training data
    UNKNOWN = "unknown"               # Couldn't classify

class QueryRouter:
    """Intelligent query routing for TTRPG Center"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Pattern-based routing rules
        self.rag_patterns = [
            r'\b(how much|price|cost|costs?)\b.*\b(gold|gp|silver|sp|copper|cp)\b',
            r'\b(what is|what are|describe|list)\b.*\b(feat|spell|item|weapon|armor)\b',
            r'\b(stats?|statistics?|ability scores?)\b.*\b(for|of)\b',
            r'\b(rules?|mechanics?)\b.*\b(for|about|of)\b',
            r'\b(page|chapter|section)\b.*\b(reference|number)\b',
            r'\b(available|legal|valid|possible)\b.*\b(options?|choices?|feats?|spells?)\b',
        ]
        
        self.workflow_patterns = [
            r'\b(create|make|build|generate)\b.*\b(character|hero|pc)\b',
            r'\b(level up|advance|level advancement)\b',
            r'\b(step by step|guide|walk me through|help me)\b.*\b(character|creation|building)\b',
            r'\b(character creation|char gen|making a character)\b',
            r'\b(multiclass|dual class|prestige class)\b',
        ]
        
        self.calculation_patterns = [
            r'\b(roll|dice|d\d+|damage|calculate)\b',
            r'\b(attack bonus|save|saving throw|skill check)\b.*\b(calculate|compute|roll)\b',
            r'\b(\d+d\d+|\dd\d+|roll \d+)\b',
            r'\b(total|sum|add|subtract|multiply)\b.*\b(bonus|modifier|score)\b',
        ]
    
    def route_query(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route query to appropriate processing method
        Returns routing decision with confidence and metadata
        """
        context = context or {}
        query_lower = query.lower().strip()
        
        logger.info(f"Routing query: {query[:50]}...")
        
        # Pattern-based classification (fast)
        pattern_result = self._classify_by_patterns(query_lower)
        
        # LLM-based classification for ambiguous cases
        if pattern_result["confidence"] < 0.7:
            llm_result = self._classify_with_llm(query, context)
            
            # Combine results (prefer LLM for low-confidence patterns)
            if llm_result["confidence"] > pattern_result["confidence"]:
                result = llm_result
            else:
                result = pattern_result
        else:
            result = pattern_result
        
        # Add routing metadata
        result.update({
            "original_query": query,
            "query_length": len(query.split()),
            "has_context": bool(context),
            "timestamp": time.time(),
            "routing_method": "hybrid"
        })
        
        logger.info(f"Routed to {result['query_type']} (confidence: {result['confidence']:.2f})")
        return result
    
    def _classify_by_patterns(self, query: str) -> Dict[str, Any]:
        """Fast pattern-based classification"""
        
        # Check workflow patterns first (higher specificity)
        workflow_matches = sum(1 for pattern in self.workflow_patterns if re.search(pattern, query))
        if workflow_matches > 0:
            confidence = min(0.8, 0.4 + (workflow_matches * 0.2))
            return {
                "query_type": QueryType.WORKFLOW,
                "confidence": confidence,
                "reasoning": f"Matched {workflow_matches} workflow patterns",
                "suggested_workflow": self._suggest_workflow(query)
            }
        
        # Check calculation patterns
        calc_matches = sum(1 for pattern in self.calculation_patterns if re.search(pattern, query))
        if calc_matches > 0:
            return {
                "query_type": QueryType.CALCULATION,
                "confidence": min(0.9, 0.5 + (calc_matches * 0.2)),
                "reasoning": f"Matched {calc_matches} calculation patterns"
            }
        
        # Check RAG patterns
        rag_matches = sum(1 for pattern in self.rag_patterns if re.search(pattern, query))
        if rag_matches > 0:
            confidence = min(0.8, 0.3 + (rag_matches * 0.15))
            return {
                "query_type": QueryType.RAG_LOOKUP,
                "confidence": confidence,
                "reasoning": f"Matched {rag_matches} RAG patterns",
                "suggested_filters": self._extract_rag_filters(query)
            }
        
        # Default to RAG with low confidence
        return {
            "query_type": QueryType.RAG_LOOKUP,
            "confidence": 0.3,
            "reasoning": "No specific patterns matched, defaulting to RAG"
        }
    
    def _classify_with_llm(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM-based classification for ambiguous queries"""
        try:
            # Build classification prompt
            system_prompt = """You are a query classifier for a TTRPG (tabletop RPG) assistant. Classify the user's query into one of these categories:

1. RAG_LOOKUP - Factual questions, rules lookups, "what is", "how much", lists of options
2. WORKFLOW - Multi-step guided tasks like character creation, level advancement, complex processes
3. CALCULATION - Math problems, dice rolls, stat calculations, attack bonuses
4. FALLBACK - Questions about general RPG concepts not in the game books

Respond with just the category name and a confidence score (0.0-1.0)."""
            
            user_prompt = f"Query: {query}"
            if context:
                user_prompt += f"\nContext: {context}"
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Extract classification and confidence
            parts = response_text.split()
            if len(parts) >= 2:
                query_type_str = parts[0]
                try:
                    confidence = float(parts[1])
                except (ValueError, IndexError):
                    confidence = 0.5
            else:
                query_type_str = response_text
                confidence = 0.5
            
            # Map to enum
            try:
                query_type = QueryType(query_type_str.lower())
            except ValueError:
                query_type = QueryType.RAG_LOOKUP
                confidence = 0.3
            
            result = {
                "query_type": query_type,
                "confidence": min(confidence, 0.95),  # Cap LLM confidence
                "reasoning": f"LLM classification: {response_text}"
            }
            
            # Add type-specific metadata
            if query_type == QueryType.WORKFLOW:
                result["suggested_workflow"] = self._suggest_workflow(query)
            elif query_type == QueryType.RAG_LOOKUP:
                result["suggested_filters"] = self._extract_rag_filters(query)
            
            return result
        
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return {
                "query_type": QueryType.RAG_LOOKUP,
                "confidence": 0.2,
                "reasoning": f"LLM classification error: {str(e)}"
            }
    
    def _suggest_workflow(self, query: str) -> Optional[str]:
        """Suggest appropriate workflow based on query content"""
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["character", "create", "build", "make"]):
            # Detect system for specific workflow
            if "pathfinder" in query_lower or "pf2e" in query_lower:
                return "character_creation_pathfinder_2e"
            else:
                return "character_creation_pathfinder_2e"  # Default for now
        
        if any(term in query_lower for term in ["level", "advance", "level up"]):
            if "pathfinder" in query_lower or "pf2e" in query_lower:
                return "level_up_pathfinder_2e"
            else:
                return "level_up_pathfinder_2e"  # Default for now
        
        return None
    
    def _extract_rag_filters(self, query: str) -> Dict[str, Any]:
        """Extract filtering hints from query for RAG search"""
        filters = {}
        query_lower = query.lower()
        
        # System detection
        if "pathfinder" in query_lower or "pf2e" in query_lower or "pf2" in query_lower:
            filters["system"] = "Pathfinder 2E"
        elif "d&d" in query_lower or "dnd" in query_lower or "dungeons" in query_lower:
            if "5e" in query_lower or "fifth" in query_lower:
                filters["system"] = "D&D 5E"
            else:
                filters["system"] = "D&D"
        
        # Content type hints
        if any(term in query_lower for term in ["spell", "magic", "cast"]):
            filters["category"] = "spells"
        elif any(term in query_lower for term in ["weapon", "armor", "equipment", "gear"]):
            filters["category"] = "equipment"
        elif any(term in query_lower for term in ["feat", "ability", "talent"]):
            filters["category"] = "feats"
        elif any(term in query_lower for term in ["class", "archetype", "subclass"]):
            filters["category"] = "classes"
        
        return filters
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics (placeholder for production metrics)"""
        return {
            "total_queries": 0,
            "rag_queries": 0,
            "workflow_queries": 0,
            "calculation_queries": 0,
            "fallback_queries": 0,
            "average_confidence": 0.0
        }

# Global instance
_router = None

def get_query_router() -> QueryRouter:
    """Get global query router instance"""
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router

# Add missing import
import time