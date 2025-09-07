# src_common/planner/budget.py
"""
Budget Management and Model Selection for Phase 3 Workflows
US-304: Cost-/Latency-Aware Action Selection implementation
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import yaml
import time

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)

@dataclass
class ModelConfig:
    """Model configuration with cost and performance characteristics"""
    name: str
    provider: str
    cost_per_1k_tokens: float
    latency_ms: int
    context_window: int
    capabilities: List[str]

@dataclass
class BudgetConstraints:
    """Budget and resource constraints for workflow planning"""
    max_total_tokens: int
    max_total_cost_usd: float
    max_time_s: int
    max_parallel_tasks: int
    user_role: str = "player"

class BudgetManager:
    """
    Manages workflow budgets and enforces cost/latency constraints
    
    Provides model selection based on task requirements and budget limits
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/budget_policies.yaml")
        
        # Default model configurations
        self.models = {
            "claude-3-haiku": ModelConfig(
                name="claude-3-haiku",
                provider="anthropic",
                cost_per_1k_tokens=0.25,
                latency_ms=800,
                context_window=200000,
                capabilities=["reasoning", "retrieval", "verification"]
            ),
            "claude-3-sonnet": ModelConfig(
                name="claude-3-sonnet", 
                provider="anthropic",
                cost_per_1k_tokens=3.0,
                latency_ms=1500,
                context_window=200000,
                capabilities=["reasoning", "synthesis", "complex_analysis"]
            ),
            "gpt-3.5-turbo": ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost_per_1k_tokens=1.0,
                latency_ms=1000,
                context_window=16000,
                capabilities=["reasoning", "retrieval", "computation"]
            ),
            "gpt-4": ModelConfig(
                name="gpt-4",
                provider="openai", 
                cost_per_1k_tokens=30.0,
                latency_ms=3000,
                context_window=8000,
                capabilities=["complex_reasoning", "synthesis", "verification"]
            ),
            "local": ModelConfig(
                name="local",
                provider="local",
                cost_per_1k_tokens=0.0,
                latency_ms=100,
                context_window=4000,
                capabilities=["computation", "formatting"]
            )
        }
        
        # Default budget policies by role
        self.default_budgets = {
            "admin": BudgetConstraints(
                max_total_tokens=100000,
                max_total_cost_usd=10.0,
                max_time_s=600,
                max_parallel_tasks=10
            ),
            "player": BudgetConstraints(
                max_total_tokens=20000,
                max_total_cost_usd=2.0,
                max_time_s=120,
                max_parallel_tasks=3
            ),
            "guest": BudgetConstraints(
                max_total_tokens=5000,
                max_total_cost_usd=0.5,
                max_time_s=30,
                max_parallel_tasks=1
            )
        }
        
        # Load custom policies if available
        self._load_policies()
    
    def _load_policies(self):
        """Load budget policies from YAML configuration"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    
                # Update model configs
                if "models" in config:
                    for model_name, model_data in config["models"].items():
                        if model_name in self.models:
                            # Update existing model
                            model = self.models[model_name]
                            model.cost_per_1k_tokens = model_data.get("cost_per_1k_tokens", model.cost_per_1k_tokens)
                            model.latency_ms = model_data.get("latency_ms", model.latency_ms)
                            model.context_window = model_data.get("context_window", model.context_window)
                            model.capabilities = model_data.get("capabilities", model.capabilities)
                        else:
                            # Add new model
                            self.models[model_name] = ModelConfig(**model_data)
                
                # Update budget policies
                if "budgets" in config:
                    for role, budget_data in config["budgets"].items():
                        self.default_budgets[role] = BudgetConstraints(
                            user_role=role,
                            **budget_data
                        )
                        
                logger.info(f"Loaded budget policies from {self.config_path}")
        
        except Exception as e:
            logger.warning(f"Could not load budget policies: {e}")
    
    def get_budget_for_role(self, role: str) -> BudgetConstraints:
        """Get budget constraints for user role"""
        return self.default_budgets.get(role, self.default_budgets["guest"])
    
    def select_model(self, task_type: str, estimated_tokens: int, priority: str = "balanced") -> str:
        """
        Select optimal model for task based on type, complexity, and priority
        
        Args:
            task_type: Type of task (retrieval, reasoning, etc.)
            estimated_tokens: Estimated token usage
            priority: "speed", "cost", "quality", or "balanced"
            
        Returns:
            Selected model name
        """
        
        # Filter models by capability
        capable_models = [
            model for model in self.models.values()
            if task_type in model.capabilities
        ]
        
        if not capable_models:
            # Fallback to general models
            capable_models = [
                model for model in self.models.values()
                if "reasoning" in model.capabilities
            ]
        
        if not capable_models:
            logger.warning(f"No capable models found for task type {task_type}")
            return "claude-3-haiku"  # Safe fallback
        
        # Score models based on priority
        def score_model(model: ModelConfig) -> float:
            if priority == "speed":
                return 1.0 / model.latency_ms
            elif priority == "cost":
                return 1.0 / model.cost_per_1k_tokens
            elif priority == "quality":
                # Prefer more expensive models for quality
                return model.cost_per_1k_tokens
            else:  # balanced
                # Balance cost, speed, and quality
                cost_score = 1.0 / model.cost_per_1k_tokens
                speed_score = 1.0 / model.latency_ms
                quality_score = model.cost_per_1k_tokens / 10  # Normalize
                
                return (cost_score + speed_score + quality_score) / 3
        
        # Select best model
        best_model = max(capable_models, key=score_model)
        
        # Check context window constraint
        if estimated_tokens > best_model.context_window * 0.9:  # 90% safety margin
            # Find model with larger context window
            large_context_models = [
                model for model in capable_models
                if model.context_window > estimated_tokens * 1.1
            ]
            if large_context_models:
                best_model = min(large_context_models, key=lambda m: m.cost_per_1k_tokens)
        
        logger.debug(f"Selected {best_model.name} for {task_type} task with {estimated_tokens} tokens")
        return best_model.name
    
    def estimate_workflow_cost(self, tasks: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Estimate total cost and time for workflow
        
        Args:
            tasks: List of task dictionaries with model and token estimates
            
        Returns:
            Dictionary with cost and time estimates
        """
        
        total_cost = 0.0
        total_time = 0
        total_tokens = 0
        
        task_costs = []
        
        for task in tasks:
            model_name = task.get("model", "claude-3-haiku")
            estimated_tokens = task.get("estimated_tokens", 1000)
            
            if model_name in self.models:
                model = self.models[model_name]
                task_cost = (estimated_tokens / 1000) * model.cost_per_1k_tokens
                task_time = model.latency_ms / 1000  # Convert to seconds
            else:
                # Unknown model, use conservative estimates
                task_cost = (estimated_tokens / 1000) * 5.0  # $5 per 1k tokens
                task_time = 2.0  # 2 seconds
            
            total_cost += task_cost
            total_time += task_time
            total_tokens += estimated_tokens
            
            task_costs.append({
                "task_id": task.get("id"),
                "model": model_name,
                "tokens": estimated_tokens,
                "cost_usd": task_cost,
                "time_s": task_time
            })
        
        return {
            "total_cost_usd": round(total_cost, 4),
            "total_time_s": round(total_time, 1),
            "total_tokens": total_tokens,
            "task_breakdown": task_costs
        }
    
    def check_budget_compliance(self, plan_estimate: Dict[str, Any], budget: BudgetConstraints) -> Tuple[bool, List[str]]:
        """
        Check if workflow plan complies with budget constraints
        
        Returns:
            (is_compliant, list_of_violations)
        """
        violations = []
        
        if plan_estimate["total_tokens"] > budget.max_total_tokens:
            violations.append(f"Token limit exceeded: {plan_estimate['total_tokens']}/{budget.max_total_tokens}")
        
        if plan_estimate["total_cost_usd"] > budget.max_total_cost_usd:
            violations.append(f"Cost limit exceeded: ${plan_estimate['total_cost_usd']}/{budget.max_total_cost_usd}")
        
        if plan_estimate["total_time_s"] > budget.max_time_s:
            violations.append(f"Time limit exceeded: {plan_estimate['total_time_s']}s/{budget.max_time_s}s")
        
        task_count = len(plan_estimate.get("task_breakdown", []))
        if task_count > budget.max_parallel_tasks:
            violations.append(f"Too many parallel tasks: {task_count}/{budget.max_parallel_tasks}")
        
        return len(violations) == 0, violations


class ModelSelector:
    """Utility class for intelligent model selection based on task characteristics"""
    
    def __init__(self, budget_manager: BudgetManager):
        self.budget_manager = budget_manager
    
    def select_for_task(self, task_type: str, complexity: str, constraints: Dict[str, Any]) -> str:
        """
        Select optimal model for a specific task
        
        Args:
            task_type: Type of task (retrieval, reasoning, etc.)
            complexity: "low", "medium", "high"
            constraints: Additional constraints (max_cost, max_latency, etc.)
            
        Returns:
            Selected model name
        """
        
        # Estimate tokens based on complexity
        token_estimates = {
            "low": 1000,
            "medium": 3000,
            "high": 8000
        }
        estimated_tokens = token_estimates.get(complexity, 3000)
        
        # Determine priority based on constraints
        if constraints.get("max_latency_ms", float('inf')) < 1000:
            priority = "speed"
        elif constraints.get("max_cost_usd", float('inf')) < 0.01:
            priority = "cost"
        elif complexity == "high":
            priority = "quality"
        else:
            priority = "balanced"
        
        return self.budget_manager.select_model(task_type, estimated_tokens, priority)
    
    def optimize_plan_models(self, plan: Dict[str, Any], budget: BudgetConstraints) -> Dict[str, Any]:
        """
        Optimize model selection for all tasks in a plan to stay within budget
        
        Args:
            plan: Workflow plan dictionary
            budget: Budget constraints to respect
            
        Returns:
            Optimized plan with updated model selections
        """
        
        optimized_plan = plan.copy()
        tasks = optimized_plan.get("tasks", [])
        
        # Calculate current cost
        current_estimate = self.budget_manager.estimate_workflow_cost(tasks)
        
        if current_estimate["total_cost_usd"] <= budget.max_total_cost_usd:
            return optimized_plan  # Already within budget
        
        # Optimize by downgrading models for less critical tasks
        # Sort tasks by importance (dependencies, task type)
        def task_importance(task):
            # Higher importance for tasks with many dependents
            dependents = sum(1 for t in tasks if task["id"] in t.get("dependencies", []))
            
            # Higher importance for reasoning/synthesis tasks
            type_weights = {
                "reasoning": 3,
                "synthesis": 3, 
                "verification": 2,
                "retrieval": 1,
                "computation": 1
            }
            type_weight = type_weights.get(task.get("type", "reasoning"), 2)
            
            return dependents + type_weight
        
        sorted_tasks = sorted(tasks, key=task_importance)
        
        # Downgrade models starting with least important tasks
        for task in sorted_tasks:
            current_model = task.get("model", "claude-3-haiku")
            
            # Try cheaper alternatives
            alternatives = self._get_cheaper_alternatives(current_model, task.get("type", "reasoning"))
            
            for alt_model in alternatives:
                # Update task model temporarily
                original_model = task["model"]
                task["model"] = alt_model
                
                # Re-estimate cost
                new_estimate = self.budget_manager.estimate_workflow_cost(tasks)
                
                if new_estimate["total_cost_usd"] <= budget.max_total_cost_usd:
                    logger.info(f"Optimized task {task['id']}: {original_model} → {alt_model}")
                    break
                else:
                    # Restore original model and try next alternative
                    task["model"] = original_model
            
            # Check if we're within budget now
            final_estimate = self.budget_manager.estimate_workflow_cost(tasks)
            if final_estimate["total_cost_usd"] <= budget.max_total_cost_usd:
                break
        
        return optimized_plan
    
    def _get_cheaper_alternatives(self, current_model: str, task_type: str) -> List[str]:
        """Get list of cheaper model alternatives for a task type"""

        # Safely resolve current model cost; unknown models treated as most expensive
        current_cfg = self.budget_manager.models.get(current_model)
        current_cost = current_cfg.cost_per_1k_tokens if isinstance(current_cfg, ModelConfig) else float('inf')

        # Find cheaper models that can handle the task type
        alternatives = []
        for model_name, model_config in self.budget_manager.models.items():
            if (model_config.cost_per_1k_tokens < current_cost and
                task_type in model_config.capabilities):
                alternatives.append(model_name)

        # Sort by cost (cheapest first)
        alternatives.sort(key=lambda m: self.budget_manager.models[m].cost_per_1k_tokens)

        return alternatives


class PolicyEnforcer:
    """Enforces budget policies and workflow constraints"""
    
    def __init__(self, budget_manager: BudgetManager):
        self.budget_manager = budget_manager
    
    def enforce_plan(self, plan: Dict[str, Any], user_role: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Enforce budget policies on a workflow plan
        
        Args:
            plan: Workflow plan to validate
            user_role: User role for budget selection
            
        Returns:
            (is_approved, response_data)
        """
        
        budget = self.budget_manager.get_budget_for_role(user_role)
        estimate = self.budget_manager.estimate_workflow_cost(plan.get("tasks", []))
        
        # Check compliance
        is_compliant, violations = self.budget_manager.check_budget_compliance(estimate, budget)
        
        response_data = {
            "plan_id": plan.get("id"),
            "estimate": estimate,
            "budget": {
                "role": user_role,
                "limits": {
                    "max_tokens": budget.max_total_tokens,
                    "max_cost_usd": budget.max_total_cost_usd,
                    "max_time_s": budget.max_time_s,
                    "max_parallel": budget.max_parallel_tasks
                }
            },
            "compliance": {
                "approved": is_compliant,
                "violations": violations
            }
        }
        
        if not is_compliant:
            logger.warning(f"Plan {plan.get('id')} violates budget: {violations}")
            
            # Try to optimize the plan
            selector = ModelSelector(self.budget_manager)
            optimized_plan = selector.optimize_plan_models(plan, budget)
            
            # Re-check optimized plan
            optimized_estimate = self.budget_manager.estimate_workflow_cost(optimized_plan.get("tasks", []))
            optimized_compliant, optimized_violations = self.budget_manager.check_budget_compliance(optimized_estimate, budget)
            
            response_data.update({
                "optimization_attempted": True,
                "optimized_estimate": optimized_estimate,
                "optimized_compliance": {
                    "approved": optimized_compliant,
                    "violations": optimized_violations
                }
            })
            
            if optimized_compliant:
                response_data["optimized_plan"] = optimized_plan
                logger.info(f"Successfully optimized plan {plan.get('id')} to meet budget")
                return True, response_data
            else:
                response_data["requires_approval"] = True
                response_data["approval_reason"] = "Plan exceeds budget limits even after optimization"
                return False, response_data
        
        return True, response_data
    
    def create_approval_checkpoint(self, plan_id: str, reason: str, estimate: Dict[str, Any]) -> Dict[str, Any]:
        """Create checkpoint requiring human approval"""
        
        checkpoint_id = f"approval:{plan_id}:{int(time.time())}"
        
        return {
            "checkpoint_id": checkpoint_id,
            "plan_id": plan_id,
            "type": "budget_approval",
            "reason": reason,
            "estimate": estimate,
            "created_at": time.time(),
            "status": "pending",
            "approval_url": f"/workflow/{plan_id}/approve?checkpoint={checkpoint_id}"
        }
