import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class NodeType(Enum):
    STEP = "step"
    DECISION = "decision"
    INPUT = "input"
    VALIDATION = "validation"
    RAG_LOOKUP = "rag_lookup"
    COMPLETION = "completion"

class EdgeCondition(Enum):
    ALWAYS = "always"
    SUCCESS = "success"
    FAILURE = "failure"
    CONDITIONAL = "conditional"

class WorkflowNode:
    """Individual node in a workflow graph"""
    
    def __init__(self, 
                 node_id: str,
                 node_type: NodeType,
                 title: str,
                 prompt: str = "",
                 required_inputs: List[str] = None,
                 expected_outputs: List[str] = None,
                 validation_rules: Dict[str, Any] = None,
                 rag_query_template: str = "",
                 metadata: Dict[str, Any] = None):
        
        self.node_id = node_id
        self.node_type = node_type
        self.title = title
        self.prompt = prompt
        self.required_inputs = required_inputs or []
        self.expected_outputs = expected_outputs or []
        self.validation_rules = validation_rules or {}
        self.rag_query_template = rag_query_template
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "prompt": self.prompt,
            "required_inputs": self.required_inputs,
            "expected_outputs": self.expected_outputs,
            "validation_rules": self.validation_rules,
            "rag_query_template": self.rag_query_template,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowNode':
        return cls(
            node_id=data["node_id"],
            node_type=NodeType(data["node_type"]),
            title=data["title"],
            prompt=data.get("prompt", ""),
            required_inputs=data.get("required_inputs", []),
            expected_outputs=data.get("expected_outputs", []),
            validation_rules=data.get("validation_rules", {}),
            rag_query_template=data.get("rag_query_template", ""),
            metadata=data.get("metadata", {})
        )

class WorkflowEdge:
    """Edge connecting workflow nodes"""
    
    def __init__(self,
                 edge_id: str,
                 from_node: str,
                 to_node: str,
                 condition: EdgeCondition,
                 condition_data: Dict[str, Any] = None):
        
        self.edge_id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition
        self.condition_data = condition_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "condition": self.condition.value,
            "condition_data": self.condition_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEdge':
        return cls(
            edge_id=data["edge_id"],
            from_node=data["from_node"],
            to_node=data["to_node"],
            condition=EdgeCondition(data["condition"]),
            condition_data=data.get("condition_data", {})
        )

class WorkflowGraph:
    """Complete workflow definition"""
    
    def __init__(self,
                 workflow_id: str,
                 name: str,
                 description: str,
                 system: str,
                 edition: str = "",
                 start_node: str = "",
                 nodes: Dict[str, WorkflowNode] = None,
                 edges: List[WorkflowEdge] = None,
                 metadata: Dict[str, Any] = None):
        
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.system = system
        self.edition = edition
        self.start_node = start_node
        self.nodes = nodes or {}
        self.edges = edges or []
        self.metadata = metadata or {}
    
    def add_node(self, node: WorkflowNode):
        """Add node to workflow"""
        self.nodes[node.node_id] = node
    
    def add_edge(self, edge: WorkflowEdge):
        """Add edge to workflow"""
        self.edges.append(edge)
    
    def get_next_nodes(self, current_node_id: str, execution_context: Dict[str, Any]) -> List[str]:
        """Get next nodes based on current state and edge conditions"""
        next_nodes = []
        
        for edge in self.edges:
            if edge.from_node == current_node_id:
                if self._evaluate_edge_condition(edge, execution_context):
                    next_nodes.append(edge.to_node)
        
        return next_nodes
    
    def _evaluate_edge_condition(self, edge: WorkflowEdge, context: Dict[str, Any]) -> bool:
        """Evaluate if edge condition is met"""
        if edge.condition == EdgeCondition.ALWAYS:
            return True
        
        if edge.condition == EdgeCondition.SUCCESS:
            return context.get("last_step_success", False)
        
        if edge.condition == EdgeCondition.FAILURE:
            return not context.get("last_step_success", True)
        
        if edge.condition == EdgeCondition.CONDITIONAL:
            # Evaluate conditional logic
            condition_key = edge.condition_data.get("key")
            condition_value = edge.condition_data.get("value")
            
            if condition_key and condition_key in context:
                return context[condition_key] == condition_value
        
        return False
    
    def validate_workflow(self) -> List[str]:
        """Validate workflow structure and return any issues"""
        issues = []
        
        # Check start node exists
        if not self.start_node or self.start_node not in self.nodes:
            issues.append("Invalid or missing start_node")
        
        # Check all edge references exist
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                issues.append(f"Edge references non-existent from_node: {edge.from_node}")
            if edge.to_node not in self.nodes:
                issues.append(f"Edge references non-existent to_node: {edge.to_node}")
        
        # Check for unreachable nodes
        reachable = set()
        if self.start_node:
            self._find_reachable_nodes(self.start_node, reachable)
        
        for node_id in self.nodes:
            if node_id not in reachable:
                issues.append(f"Node {node_id} is unreachable")
        
        return issues
    
    def _find_reachable_nodes(self, node_id: str, reachable: set):
        """Recursively find reachable nodes"""
        if node_id in reachable:
            return
        
        reachable.add(node_id)
        
        for edge in self.edges:
            if edge.from_node == node_id:
                self._find_reachable_nodes(edge.to_node, reachable)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "system": self.system,
            "edition": self.edition,
            "start_node": self.start_node,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowGraph':
        workflow = cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            description=data["description"],
            system=data["system"],
            edition=data.get("edition", ""),
            start_node=data.get("start_node", ""),
            metadata=data.get("metadata", {})
        )
        
        # Load nodes
        for node_data in data.get("nodes", {}).values():
            workflow.add_node(WorkflowNode.from_dict(node_data))
        
        # Load edges
        for edge_data in data.get("edges", []):
            workflow.add_edge(WorkflowEdge.from_dict(edge_data))
        
        return workflow

class WorkflowExecution:
    """Runtime execution state for a workflow"""
    
    def __init__(self, workflow: WorkflowGraph, execution_id: str = None):
        self.workflow = workflow
        self.execution_id = execution_id or str(uuid.uuid4())
        self.current_node = workflow.start_node
        self.context = {}
        self.step_history = []
        self.status = "started"
        self.start_time = time.time()
        self.end_time = None
    
    def get_current_node(self) -> Optional[WorkflowNode]:
        """Get current node object"""
        return self.workflow.nodes.get(self.current_node)
    
    def move_to_next_node(self, step_result: Dict[str, Any]) -> bool:
        """Move to next node based on step result"""
        # Record step in history
        self.step_history.append({
            "node_id": self.current_node,
            "timestamp": time.time(),
            "result": step_result.copy()
        })
        
        # Update context
        self.context.update(step_result.get("context_updates", {}))
        self.context["last_step_success"] = step_result.get("success", False)
        
        # Find next nodes
        next_nodes = self.workflow.get_next_nodes(self.current_node, self.context)
        
        if not next_nodes:
            # No more nodes - workflow complete
            self.status = "completed"
            self.end_time = time.time()
            return False
        
        if len(next_nodes) == 1:
            # Single next node
            self.current_node = next_nodes[0]
            return True
        
        # Multiple next nodes - need user decision or error
        self.status = "needs_decision"
        self.context["decision_options"] = next_nodes
        return True
    
    def choose_path(self, chosen_node: str) -> bool:
        """Manually choose next node when multiple options exist"""
        if self.status != "needs_decision":
            return False
        
        if chosen_node in self.context.get("decision_options", []):
            self.current_node = chosen_node
            self.status = "active"
            return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow.workflow_id,
            "current_node": self.current_node,
            "context": self.context,
            "step_history": self.step_history,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time
        }

class WorkflowEngine:
    """Main workflow execution engine"""
    
    def __init__(self, workflow_dir: str = "app/workflows/definitions"):
        self.workflow_dir = Path(workflow_dir)
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        self.workflows: Dict[str, WorkflowGraph] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.load_workflows()
    
    def load_workflows(self):
        """Load all workflow definitions from disk"""
        try:
            for workflow_file in self.workflow_dir.glob("*.json"):
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    workflow = WorkflowGraph.from_dict(data)
                    self.workflows[workflow.workflow_id] = workflow
            
            logger.info(f"Loaded {len(self.workflows)} workflow definitions")
        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
    
    def save_workflow(self, workflow: WorkflowGraph):
        """Save workflow definition to disk"""
        try:
            file_path = self.workflow_dir / f"{workflow.workflow_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(workflow.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.workflows[workflow.workflow_id] = workflow
            logger.info(f"Saved workflow: {workflow.workflow_id}")
        except Exception as e:
            logger.error(f"Failed to save workflow {workflow.workflow_id}: {e}")
    
    def start_workflow(self, workflow_id: str, initial_context: Dict[str, Any] = None) -> Optional[str]:
        """Start a new workflow execution"""
        if workflow_id not in self.workflows:
            logger.error(f"Workflow not found: {workflow_id}")
            return None
        
        workflow = self.workflows[workflow_id]
        execution = WorkflowExecution(workflow)
        
        if initial_context:
            execution.context.update(initial_context)
        
        self.active_executions[execution.execution_id] = execution
        
        logger.info(f"Started workflow execution: {execution.execution_id}")
        return execution.execution_id
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID"""
        return self.active_executions.get(execution_id)
    
    def list_workflows(self, system: str = None) -> List[Dict[str, Any]]:
        """List available workflows, optionally filtered by system"""
        workflows = []
        for workflow in self.workflows.values():
            if system is None or workflow.system.lower() == system.lower():
                workflows.append({
                    "workflow_id": workflow.workflow_id,
                    "name": workflow.name,
                    "description": workflow.description,
                    "system": workflow.system,
                    "edition": workflow.edition
                })
        return workflows
    
    def cleanup_completed_executions(self, max_age_hours: int = 24):
        """Remove old completed executions"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        to_remove = []
        
        for exec_id, execution in self.active_executions.items():
            if (execution.status in ["completed", "failed"] and 
                execution.end_time and 
                execution.end_time < cutoff_time):
                to_remove.append(exec_id)
        
        for exec_id in to_remove:
            del self.active_executions[exec_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old executions")

# Global instance
_workflow_engine = None

def get_workflow_engine() -> WorkflowEngine:
    """Get global workflow engine instance"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine