# src_common/planner/plan.py
"""
Task Planner - Graph-aware workflow planning and DAG generation
US-303: Task Planner (Graph-Aware) implementation
"""

import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from ..ttrpg_logging import get_logger
from ..graph.store import GraphStore, NodeType, EdgeType

logger = get_logger(__name__)

@dataclass
class WorkflowTask:
    """Individual task in a workflow plan"""
    id: str
    type: str
    name: str
    description: str
    dependencies: List[str]
    tool: str
    model: str
    prompt: str
    parameters: Dict[str, Any]
    estimated_tokens: int
    estimated_time_s: int
    requires_approval: bool = False
    checkpoint: bool = False
    
@dataclass 
class WorkflowPlan:
    """Complete workflow plan with tasks and metadata"""
    id: str
    goal: str
    procedure_id: Optional[str]
    tasks: List[WorkflowTask]
    edges: List[Tuple[str, str]]  # (source_task_id, target_task_id)
    total_estimated_tokens: int
    total_estimated_time_s: int
    checkpoints: List[str]  # task_ids requiring approval
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary format"""
        return {
            "id": self.id,
            "goal": self.goal,
            "procedure_id": self.procedure_id,
            "tasks": [asdict(task) for task in self.tasks],
            "edges": self.edges,
            "total_estimated_tokens": self.total_estimated_tokens,
            "total_estimated_time_s": self.total_estimated_time_s,
            "checkpoints": self.checkpoints,
            "created_at": self.created_at
        }

class TaskPlanner:
    """
    Graph-aware task planner that converts goals into executable workflow plans
    
    Uses knowledge graph to find relevant procedures and decompose into tasks
    """
    
    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store
        
        # Budget constraints
        self.MAX_TOKENS = 50000
        self.MAX_TIME_S = 300
        self.MAX_TASKS = 20
        
        # Model/tool mappings for different task types
        self.tool_mappings = {
            "retrieval": {"tool": "retriever", "model": "claude-3-haiku", "base_tokens": 1000},
            "reasoning": {"tool": "llm", "model": "claude-3-sonnet", "base_tokens": 2000},
            "computation": {"tool": "calculator", "model": "local", "base_tokens": 100},
            "verification": {"tool": "rules_checker", "model": "claude-3-haiku", "base_tokens": 500},
            "synthesis": {"tool": "llm", "model": "claude-3-sonnet", "base_tokens": 3000}
        }

    def _sanitize(self, text: str) -> str:
        """Basic sanitization to strip dangerous substrings from prompts/descriptions."""
        if not text:
            return ""
        lowered = str(text)
        dangerous = [
            "rm -rf", "cat /etc", "<script>", "</script>",
            "eval(", "system(", "exec(", "&&", "||",
        ]
        for pat in dangerous:
            lowered = lowered.replace(pat, "[filtered]")
        return lowered
    
    def plan_from_goal(self, goal: str, constraints: Optional[Dict[str, Any]] = None) -> WorkflowPlan:
        """
        Create a workflow plan from a goal using graph-aware decomposition
        
        Args:
            goal: User goal statement
            constraints: Optional constraints (budget, models, etc.)
            
        Returns:
            WorkflowPlan with tasks and dependencies
        """
        logger.info(f"Planning workflow for goal: {goal[:100]}...")
        
        try:
            # Apply constraints
            constraints = constraints or {}
            max_tokens = constraints.get("max_tokens", self.MAX_TOKENS)
            max_time = constraints.get("max_time_s", self.MAX_TIME_S)
            
            # Step 1: Find relevant procedure from graph
            procedure = self._select_procedure(goal)
            
            # Step 2: Expand procedure into steps  
            steps = self._expand_steps(procedure) if procedure else []
            
            # Step 3: Create task DAG with dependencies
            tasks, edges = self._create_task_dag(goal, procedure, steps)
            
            # Step 4: Assign tools and models
            self._assign_tools_and_models(tasks)
            
            # Step 5: Estimate costs and identify checkpoints
            total_tokens, total_time, checkpoints = self._estimate_and_checkpoint(tasks, max_tokens, max_time)
            
            # Generate plan ID
            plan_id = f"plan:{hashlib.sha256(f'{goal}:{time.time()}'.encode()).hexdigest()[:16]}"
            
            plan = WorkflowPlan(
                id=plan_id,
                goal=goal,
                procedure_id=procedure["id"] if procedure else None,
                tasks=tasks,
                edges=edges,
                total_estimated_tokens=total_tokens,
                total_estimated_time_s=total_time,
                checkpoints=checkpoints,
                created_at=time.time()
            )
            
            logger.info(f"Created plan {plan_id} with {len(tasks)} tasks, {total_tokens} tokens estimated")
            return plan
            
        except Exception as e:
            logger.error(f"Error planning workflow: {e}")
            # Return minimal fallback plan
            fallback_task = WorkflowTask(
                id="task:fallback:1",
                type="reasoning",
                name="Direct Answer",
                description=f"Provide direct answer to: {goal}",
                dependencies=[],
                tool="llm",
                model="claude-3-haiku",
                prompt=f"Answer this query directly: {goal}",
                parameters={},
                estimated_tokens=1000,
                estimated_time_s=10
            )
            
            return WorkflowPlan(
                id=f"plan:fallback:{int(time.time())}",
                goal=goal,
                procedure_id=None,
                tasks=[fallback_task],
                edges=[],
                total_estimated_tokens=1000,
                total_estimated_time_s=10,
                checkpoints=[],
                created_at=time.time()
            )
    
    def _select_procedure(self, goal: str) -> Optional[Dict[str, Any]]:
        """Find best matching procedure from graph for the goal"""
        
        # Query graph for procedures
        procedures = self.graph_store.query(
            "MATCH (n:Procedure) WHERE n.property = $param",
            {}  # Basic query - would be more sophisticated in real implementation
        )
        
        if not procedures:
            logger.debug("No procedures found in graph")
            return None
        
        # Simple scoring based on name/description overlap
        goal_words = set(goal.lower().split())
        best_score = 0
        best_procedure = None
        
        for proc in procedures:
            props = proc.get("properties", {})
            proc_text = f"{props.get('name', '')} {props.get('description', '')}".lower()
            proc_words = set(proc_text.split())
            
            # Jaccard similarity
            intersection = len(goal_words & proc_words)
            union = len(goal_words | proc_words)
            score = intersection / union if union > 0 else 0
            
            if score > best_score:
                best_score = score
                best_procedure = proc
        
        if best_procedure and best_score > 0.1:  # Minimum threshold
            logger.debug(f"Selected procedure {best_procedure['id']} with score {best_score:.2f}")
            return best_procedure
        
        logger.debug("No suitable procedure found, will create generic tasks")
        return None
    
    def _expand_steps(self, procedure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Expand procedure into constituent steps using graph traversal"""
        
        if not procedure:
            return []
        
        # Find steps that are part of this procedure
        steps = []
        neighbors = self.graph_store.neighbors(procedure["id"], etypes=["part_of"], depth=1)
        
        for neighbor in neighbors:
            if neighbor.get("type") == "Step":
                steps.append(neighbor)
        
        # Sort by step number if available
        def sort_key(step):
            props = step.get("properties", {})
            return props.get("step_number", 999)
        
        steps.sort(key=sort_key)
        logger.debug(f"Expanded procedure {procedure['id']} into {len(steps)} steps")
        return steps
    
    def _create_task_dag(self, goal: str, procedure: Optional[Dict], steps: List[Dict]) -> Tuple[List[WorkflowTask], List[Tuple[str, str]]]:
        """Create task DAG from procedure steps or goal directly"""
        
        tasks = []
        edges = []
        
        if steps:
            # Create tasks from procedure steps
            for i, step in enumerate(steps):
                step_props = step.get("properties", {})
                task_id = f"task:{step['id']}"
                
                # Determine task type from step content
                step_name = step_props.get("name", "")
                task_type = self._classify_step_type(step_name, step_props.get("description", ""))
                
                task = WorkflowTask(
                    id=task_id,
                    type=task_type,
                    name=step_name,
                    description=step_props.get("description", ""),
                    dependencies=[],  # Will be filled in next
                    tool="",  # Will be assigned later
                    model="",  # Will be assigned later
                    prompt="",  # Will be assigned later
                    parameters={"step_number": step_props.get("step_number", i+1)},
                    estimated_tokens=0,  # Will be estimated later
                    estimated_time_s=0  # Will be estimated later
                )
                tasks.append(task)
                
                # Create dependency edges (sequential for now)
                if i > 0:
                    prev_task_id = f"task:{steps[i-1]['id']}"
                    edges.append((prev_task_id, task_id))
        else:
            # Create generic tasks for goal without procedure
            tasks = self._create_generic_tasks(goal)
            edges = self._create_generic_edges(tasks)
        
        return tasks, edges
    
    def _classify_step_type(self, step_name: str, description: str) -> str:
        """Classify step into task type for tool/model assignment"""
        
        content = f"{step_name} {description}".lower()
        
        if any(word in content for word in ["gather", "collect", "find", "search", "look up"]):
            return "retrieval"
        elif any(word in content for word in ["calculate", "compute", "roll", "dc", "bonus"]):
            return "computation"
        elif any(word in content for word in ["check", "verify", "validate", "confirm"]):
            return "verification"
        elif any(word in content for word in ["decide", "choose", "select", "pick"]):
            return "reasoning"
        else:
            return "synthesis"
    
    def _create_generic_tasks(self, goal: str) -> List[WorkflowTask]:
        """Create generic task sequence when no procedure is found"""
        
        safe_goal = self._sanitize(goal)

        tasks = [
            WorkflowTask(
                id="task:retrieve:1",
                type="retrieval",
                name="Gather Information",
                description=f"Retrieve relevant information for: {safe_goal}",
                dependencies=[],
                tool="",
                model="",
                prompt="",
                parameters={"query": safe_goal},
                estimated_tokens=0,
                estimated_time_s=0
            ),
            WorkflowTask(
                id="task:reason:1",
                type="reasoning", 
                name="Analyze and Plan",
                description=f"Analyze retrieved information and plan approach",
                dependencies=["task:retrieve:1"],
                tool="",
                model="",
                prompt="",
                parameters={},
                estimated_tokens=0,
                estimated_time_s=0
            ),
            WorkflowTask(
                id="task:synthesize:1",
                type="synthesis",
                name="Generate Answer",
                description=f"Synthesize final answer for: {safe_goal}",
                dependencies=["task:reason:1"],
                tool="",
                model="",
                prompt="",
                parameters={},
                estimated_tokens=0,
                estimated_time_s=0
            )
        ]
        
        return tasks
    
    def _create_generic_edges(self, tasks: List[WorkflowTask]) -> List[Tuple[str, str]]:
        """Create dependency edges for generic task sequence"""
        edges = []
        for i in range(1, len(tasks)):
            edges.append((tasks[i-1].id, tasks[i].id))
        return edges
    
    def _assign_tools_and_models(self, tasks: List[WorkflowTask]):
        """Assign appropriate tools and models to tasks based on type"""
        
        for task in tasks:
            mapping = self.tool_mappings.get(task.type, self.tool_mappings["reasoning"])
            task.tool = mapping["tool"]
            task.model = mapping["model"]
            
            # Generate appropriate prompt based on task type
            if task.type == "retrieval":
                task.prompt = f"Retrieve information relevant to: {task.description}"
            elif task.type == "computation":
                task.prompt = f"Compute required values for: {task.description}"
            elif task.type == "verification":
                task.prompt = f"Verify and validate: {task.description}"
            elif task.type == "reasoning":
                task.prompt = f"Analyze and reason about: {task.description}"
            else:  # synthesis
                task.prompt = f"Synthesize comprehensive answer for: {task.description}"
    
    def _estimate_and_checkpoint(self, tasks: List[WorkflowTask], max_tokens: int, max_time: int) -> Tuple[int, int, List[str]]:
        """Estimate costs and identify checkpoint requirements"""
        
        total_tokens = 0
        total_time = 0
        checkpoints = []
        
        for task in tasks:
            # Estimate tokens based on task type and complexity
            mapping = self.tool_mappings.get(task.type, self.tool_mappings["reasoning"])
            base_tokens = mapping["base_tokens"]
            
            # Factor in task complexity
            complexity_factor = len(task.description.split()) / 10  # Rough heuristic
            estimated_tokens = int(base_tokens * (1 + complexity_factor))
            
            task.estimated_tokens = estimated_tokens
            task.estimated_time_s = estimated_tokens // 100  # ~100 tokens per second estimate
            
            total_tokens += estimated_tokens
            total_time += task.estimated_time_s
            
            # Mark for checkpoint if high cost or reasoning task
            if estimated_tokens > 5000 or task.type == "reasoning":
                task.requires_approval = True
                task.checkpoint = True
                checkpoints.append(task.id)
        
        # If exceeding budgets, mark additional checkpoints
        if total_tokens > max_tokens * 0.8:
            logger.warning(f"Plan exceeds 80% of token budget ({total_tokens}/{max_tokens})")
            # Mark most expensive tasks for approval
            sorted_tasks = sorted(tasks, key=lambda t: t.estimated_tokens, reverse=True)
            for task in sorted_tasks[:3]:  # Top 3 most expensive
                if task.id not in checkpoints:
                    task.requires_approval = True
                    task.checkpoint = True
                    checkpoints.append(task.id)

        # Hard cap to protect against resource exhaustion: clamp to <= 2x budgets
        token_cap = max(1, max_tokens * 2)
        time_cap = max(1, max_time * 2)
        scale_tokens = token_cap / max(1, total_tokens)
        scale_time = time_cap / max(1, total_time)
        scale = min(1.0, scale_tokens, scale_time)
        if scale < 1.0:
            # Scale totals
            total_tokens = int(total_tokens * scale)
            total_time = int(total_time * scale)
            # Scale individual task estimates proportionally for consistency
            for task in tasks:
                task.estimated_tokens = max(1, int(task.estimated_tokens * scale))
                task.estimated_time_s = max(1, int(task.estimated_time_s * scale))

        return total_tokens, total_time, checkpoints
    
    def validate_plan(self, plan: WorkflowPlan) -> Tuple[bool, List[str]]:
        """
        Validate plan for cycles, dependencies, and budget constraints
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Check for cycles using DFS
            if self._has_cycles(plan.tasks, plan.edges):
                errors.append("Plan contains dependency cycles")
            
            # Check task limit
            if len(plan.tasks) > self.MAX_TASKS:
                errors.append(f"Plan has {len(plan.tasks)} tasks, max allowed is {self.MAX_TASKS}")
            
            # Check token budget
            if plan.total_estimated_tokens > self.MAX_TOKENS:
                errors.append(f"Plan exceeds token budget: {plan.total_estimated_tokens}/{self.MAX_TOKENS}")
            
            # Check time budget  
            if plan.total_estimated_time_s > self.MAX_TIME_S:
                errors.append(f"Plan exceeds time budget: {plan.total_estimated_time_s}/{self.MAX_TIME_S}")
            
            # Validate task dependencies exist
            task_ids = {task.id for task in plan.tasks}
            for task in plan.tasks:
                for dep in task.dependencies:
                    if dep not in task_ids:
                        errors.append(f"Task {task.id} depends on non-existent task {dep}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Error validating plan: {e}")
            return False, [f"Validation error: {e}"]
    
    def _has_cycles(self, tasks: List[WorkflowTask], edges: List[Tuple[str, str]]) -> bool:
        """Detect cycles in task dependency graph using DFS"""
        
        # Build adjacency list
        graph = {task.id: [] for task in tasks}
        for source, target in edges:
            if source in graph and target in graph:
                graph[source].append(target)
        
        # DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def has_cycle_util(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle_util(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task_id in graph:
            if task_id not in visited:
                if has_cycle_util(task_id):
                    return True
        
        return False


# Convenience function for API compatibility
def plan_from_goal(goal: str, graph: GraphStore, constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create workflow plan from goal (API-compatible function)
    
    Args:
        goal: User goal statement
        graph: Graph store instance
        constraints: Optional budget/model constraints
        
    Returns:
        Plan dictionary matching Phase 3 specification
    """
    planner = TaskPlanner(graph)
    plan = planner.plan_from_goal(goal, constraints)
    
    return plan.to_dict()
