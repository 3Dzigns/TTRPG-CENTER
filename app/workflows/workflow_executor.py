import logging
import time
from typing import Dict, List, Any, Optional
import openai
import os
from app.common.astra_client import get_vector_store
from app.common.embeddings import get_embedding_service
from .graph_engine import WorkflowExecution, WorkflowNode, NodeType

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """Executes workflow nodes and manages state transitions"""
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.embedding_service = get_embedding_service()
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def execute_node(self, 
                    execution: WorkflowExecution, 
                    user_input: str = "",
                    additional_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute current node in workflow
        Returns step result with success status and context updates
        """
        current_node = execution.get_current_node()
        if not current_node:
            return {
                "success": False,
                "error": "No current node found",
                "response": "Workflow error: invalid state"
            }
        
        logger.info(f"Executing node {current_node.node_id} ({current_node.node_type.value})")
        
        # Prepare execution context
        exec_context = execution.context.copy()
        if additional_context:
            exec_context.update(additional_context)
        exec_context["user_input"] = user_input
        
        # Execute based on node type
        if current_node.node_type == NodeType.STEP:
            return self._execute_step_node(current_node, exec_context)
        
        elif current_node.node_type == NodeType.RAG_LOOKUP:
            return self._execute_rag_node(current_node, exec_context)
        
        elif current_node.node_type == NodeType.INPUT:
            return self._execute_input_node(current_node, exec_context)
        
        elif current_node.node_type == NodeType.VALIDATION:
            return self._execute_validation_node(current_node, exec_context)
        
        elif current_node.node_type == NodeType.DECISION:
            return self._execute_decision_node(current_node, exec_context)
        
        elif current_node.node_type == NodeType.COMPLETION:
            return self._execute_completion_node(current_node, exec_context)
        
        else:
            return {
                "success": False,
                "error": f"Unknown node type: {current_node.node_type}",
                "response": "Internal workflow error"
            }
    
    def _execute_step_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a basic step node"""
        try:
            # Format prompt with context variables
            formatted_prompt = self._format_prompt(node.prompt, context)
            
            # Generate response using OpenAI
            response = self._generate_response(formatted_prompt, context)
            
            # Extract any structured data from user input
            context_updates = self._extract_context_updates(node, context)
            
            return {
                "success": True,
                "response": response,
                "context_updates": context_updates,
                "node_type": "step"
            }
        
        except Exception as e:
            logger.error(f"Step node execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I encountered an error processing this step. Please try again."
            }
    
    def _execute_rag_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a RAG lookup node"""
        try:
            # Format RAG query with context
            rag_query = self._format_prompt(node.rag_query_template, context)
            
            # Perform vector search
            query_embedding = self.embedding_service.get_embedding(rag_query)
            
            # Apply system filter if available
            filters = {}
            if "system" in context:
                filters["system"] = context["system"]
            
            search_results = self.vector_store.similarity_search(
                query_embedding, 
                k=6,
                filters=filters
            )
            
            # Format RAG results for context
            rag_context = self._format_rag_results(search_results)
            
            # Generate response using RAG context + node prompt
            full_prompt = f"{node.prompt}\n\nRelevant Information:\n{rag_context}"
            formatted_prompt = self._format_prompt(full_prompt, context)
            
            response = self._generate_response(formatted_prompt, context, rag_results=search_results)
            
            # Extract context updates
            context_updates = self._extract_context_updates(node, context)
            context_updates["rag_results"] = search_results
            context_updates["rag_query"] = rag_query
            
            return {
                "success": True,
                "response": response,
                "context_updates": context_updates,
                "node_type": "rag_lookup",
                "sources": [{"page": r["page"], "source_id": r["source_id"]} for r in search_results]
            }
        
        except Exception as e:
            logger.error(f"RAG node execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I had trouble looking up information. Please try again."
            }
    
    def _execute_input_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an input collection node"""
        try:
            user_input = context.get("user_input", "")
            
            # Validate input if rules provided
            if node.validation_rules:
                validation_result = self._validate_input(user_input, node.validation_rules)
                if not validation_result["valid"]:
                    return {
                        "success": False,
                        "response": f"Invalid input: {validation_result['error']}. Please try again.",
                        "validation_error": True
                    }
            
            # Process and store input
            context_updates = {}
            for output_key in node.expected_outputs:
                if output_key in ["current_level", "target_level"]:
                    # Parse numeric inputs
                    try:
                        value = int(user_input.strip())
                        context_updates[output_key] = value
                        if output_key == "current_level":
                            context_updates["target_level"] = value + 1
                    except ValueError:
                        return {
                            "success": False,
                            "response": "Please enter a valid number for the level.",
                            "validation_error": True
                        }
                else:
                    context_updates[output_key] = user_input.strip()
            
            # Generate confirmation response
            formatted_prompt = self._format_prompt(node.prompt, context)
            response = f"{formatted_prompt}\n\nThank you! I've recorded your input: {user_input}"
            
            return {
                "success": True,
                "response": response,
                "context_updates": context_updates,
                "node_type": "input"
            }
        
        except Exception as e:
            logger.error(f"Input node execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Error processing your input. Please try again."
            }
    
    def _execute_validation_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a validation node"""
        # Placeholder - validate context against rules
        return {
            "success": True,
            "response": "Validation passed.",
            "context_updates": {},
            "node_type": "validation"
        }
    
    def _execute_decision_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a decision node"""
        # Placeholder - present options to user
        formatted_prompt = self._format_prompt(node.prompt, context)
        
        return {
            "success": True,
            "response": formatted_prompt,
            "context_updates": {"awaiting_decision": True},
            "node_type": "decision"
        }
    
    def _execute_completion_node(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a completion node"""
        try:
            # Generate final summary/completion response
            formatted_prompt = self._format_prompt(node.prompt, context)
            response = self._generate_response(formatted_prompt, context)
            
            # Mark workflow as complete
            context_updates = {"workflow_completed": True}
            
            # Generate final outputs based on expected_outputs
            for output_key in node.expected_outputs:
                if output_key == "character_sheet":
                    context_updates[output_key] = self._generate_character_sheet(context)
                elif output_key == "updated_character":
                    context_updates[output_key] = self._generate_character_update(context)
            
            return {
                "success": True,
                "response": response,
                "context_updates": context_updates,
                "node_type": "completion",
                "workflow_complete": True
            }
        
        except Exception as e:
            logger.error(f"Completion node execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Error completing workflow. Please review your choices."
            }
    
    def _format_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """Format prompt template with context variables"""
        try:
            # Simple template replacement
            formatted = prompt
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in formatted:
                    formatted = formatted.replace(placeholder, str(value))
            
            return formatted
        except Exception as e:
            logger.warning(f"Prompt formatting error: {e}")
            return prompt
    
    def _generate_response(self, 
                          prompt: str, 
                          context: Dict[str, Any], 
                          rag_results: List[Dict[str, Any]] = None) -> str:
        """Generate response using OpenAI"""
        try:
            # Build system message
            system_message = "You are a helpful TTRPG assistant guiding users through character creation and game mechanics. Be encouraging, clear, and provide specific actionable guidance."
            
            # Add RAG context if available
            if rag_results:
                rag_context = "\n".join([f"Source: {r['source_id']} (page {r['page']}): {r['text'][:200]}..." 
                                       for r in rag_results[:3]])
                system_message += f"\n\nRelevant game rules:\n{rag_context}"
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"OpenAI response generation failed: {e}")
            return "I'm having trouble generating a response. Please try again."
    
    def _format_rag_results(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG search results for prompt context"""
        if not results:
            return "No specific information found."
        
        formatted = []
        for i, result in enumerate(results[:4]):  # Limit to top 4 results
            formatted.append(f"{i+1}. {result['text'][:300]}{'...' if len(result['text']) > 300 else ''}")
        
        return "\n\n".join(formatted)
    
    def _extract_context_updates(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract context updates from user input and node execution"""
        updates = {}
        user_input = context.get("user_input", "").strip().lower()
        
        # Simple keyword extraction based on expected outputs
        for output_key in node.expected_outputs:
            if output_key.endswith("_choice"):
                # Extract choice from user input
                if user_input and user_input not in ["yes", "no", "help"]:
                    updates[output_key] = context.get("user_input", "").strip()
            elif output_key.endswith("_ready"):
                updates[output_key] = user_input in ["yes", "y", "ready", "continue"]
        
        return updates
    
    def _validate_input(self, input_value: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user input against rules"""
        try:
            if rules.get("required", False) and not input_value.strip():
                return {"valid": False, "error": "This field is required"}
            
            if rules.get("type") == "integer":
                try:
                    value = int(input_value)
                    if "min" in rules and value < rules["min"]:
                        return {"valid": False, "error": f"Value must be at least {rules['min']}"}
                    if "max" in rules and value > rules["max"]:
                        return {"valid": False, "error": f"Value must be at most {rules['max']}"}
                except ValueError:
                    return {"valid": False, "error": "Must be a valid number"}
            
            return {"valid": True}
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {"valid": False, "error": "Validation failed"}
    
    def _generate_character_sheet(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final character sheet from workflow context"""
        # Placeholder character sheet generation
        return {
            "ancestry": context.get("ancestry_choice", "Unknown"),
            "background": context.get("background_choice", "Unknown"),
            "class": context.get("class_choice", "Unknown"),
            "level": 1,
            "abilities": context.get("final_abilities", {}),
            "feats": context.get("selected_feats", []),
            "equipment": context.get("equipment_list", []),
            "hit_points": 10,  # Placeholder
            "armor_class": 10,  # Placeholder
            "created_at": time.time()
        }
    
    def _generate_character_update(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate character updates for level advancement"""
        return {
            "previous_level": context.get("current_level", 1),
            "new_level": context.get("target_level", 2),
            "benefits_gained": context.get("level_benefits", []),
            "updated_at": time.time()
        }

# Global instance  
_executor = None

def get_workflow_executor() -> WorkflowExecutor:
    """Get global workflow executor instance"""
    global _executor
    if _executor is None:
        _executor = WorkflowExecutor()
    return _executor