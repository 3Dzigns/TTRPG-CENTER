# src_common/reason/executors.py
"""
Procedural Executors - Specialized executors for TTRPG procedures
US-309: Procedural Executors (Checklists & Guards) implementation
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)

@dataclass
class ExecutorResult:
    """Base result from procedural executors"""
    success: bool
    result: Any
    errors: List[str]
    warnings: List[str]
    sources: List[Dict[str, Any]]
    execution_time_s: float

class ChecklistExecutor:
    """
    Executes checklist-style procedures with step-by-step validation
    
    Ensures all required steps are completed and conditions are met
    """
    
    def __init__(self, graph_store=None):
        self.graph_store = graph_store
    
    def execute_checklist(self, procedure_id: str, context: Dict[str, Any]) -> ExecutorResult:
        """
        Execute a checklist procedure
        
        Args:
            procedure_id: ID of procedure to execute
            context: Input context and parameters
            
        Returns:
            ExecutorResult with checklist completion status
        """
        
        import time
        start_time = time.time()
        
        logger.info(f"Executing checklist procedure: {procedure_id}")
        
        try:
            errors = []
            warnings = []
            sources = []
            
            # Get procedure steps from graph
            if self.graph_store:
                steps = self._get_procedure_steps(procedure_id)
            else:
                steps = self._mock_procedure_steps(procedure_id)
            
            if not steps:
                errors.append(f"No steps found for procedure {procedure_id}")
                return ExecutorResult(
                    success=False,
                    result=None,
                    errors=errors,
                    warnings=warnings,
                    sources=sources,
                    execution_time_s=time.time() - start_time
                )
            
            # Execute each step in order
            checklist_results = []
            
            for step in steps:
                step_result = self._execute_checklist_step(step, context)
                checklist_results.append(step_result)
                
                # Collect sources
                if step_result.get("sources"):
                    sources.extend(step_result["sources"])
                
                # Check for blocking errors
                if not step_result["completed"]:
                    if step_result.get("required", True):
                        errors.append(f"Required step failed: {step['name']}")
                    else:
                        warnings.append(f"Optional step skipped: {step['name']}")
            
            # Determine overall success
            required_steps = [r for r in checklist_results if r.get("required", True)]
            completed_required = [r for r in required_steps if r["completed"]]
            
            success = len(completed_required) == len(required_steps)
            
            result = {
                "procedure_id": procedure_id,
                "total_steps": len(steps),
                "completed_steps": len([r for r in checklist_results if r["completed"]]),
                "required_steps": len(required_steps),
                "completed_required": len(completed_required),
                "success_rate": len(completed_required) / len(required_steps) if required_steps else 1.0,
                "checklist": checklist_results
            }
            
            return ExecutorResult(
                success=success,
                result=result,
                errors=errors,
                warnings=warnings,
                sources=sources,
                execution_time_s=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Error executing checklist {procedure_id}: {e}")
            return ExecutorResult(
                success=False,
                result=None,
                errors=[str(e)],
                warnings=[],
                sources=[],
                execution_time_s=time.time() - start_time
            )
    
    def _get_procedure_steps(self, procedure_id: str) -> List[Dict[str, Any]]:
        """Get ordered steps for a procedure from graph"""
        
        if not self.graph_store:
            return []
        
        # Find steps that are part of this procedure
        neighbors = self.graph_store.neighbors(procedure_id, etypes=["part_of"], depth=1)
        
        steps = []
        for neighbor in neighbors:
            if neighbor.get("type") == "Step":
                steps.append({
                    "id": neighbor["id"],
                    "name": neighbor.get("properties", {}).get("name", ""),
                    "description": neighbor.get("properties", {}).get("description", ""),
                    "step_number": neighbor.get("properties", {}).get("step_number", 999),
                    "required": neighbor.get("properties", {}).get("required", True)
                })
        
        # Sort by step number
        steps.sort(key=lambda s: s["step_number"])
        return steps
    
    def _mock_procedure_steps(self, procedure_id: str) -> List[Dict[str, Any]]:
        """Mock procedure steps for development"""
        
        # Generate mock steps based on procedure ID
        if "craft" in procedure_id.lower():
            return [
                {"id": "step:1", "name": "Gather Materials", "description": "Collect required reagents", "step_number": 1, "required": True},
                {"id": "step:2", "name": "Prepare Workspace", "description": "Set up crafting station", "step_number": 2, "required": True},
                {"id": "step:3", "name": "Follow Recipe", "description": "Execute crafting procedure", "step_number": 3, "required": True},
                {"id": "step:4", "name": "Quality Check", "description": "Verify final product", "step_number": 4, "required": False}
            ]
        else:
            return [
                {"id": "step:1", "name": "Generic Step 1", "description": "First step", "step_number": 1, "required": True},
                {"id": "step:2", "name": "Generic Step 2", "description": "Second step", "step_number": 2, "required": True}
            ]
    
    def _execute_checklist_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute individual checklist step"""
        
        step_name = step.get("name", "")
        step_desc = step.get("description", "")
        
        # Simple heuristics for step completion (in production, would be more sophisticated)
        completed = True  # Optimistic default
        details = f"Executed step: {step_name}"
        
        # Check for completion criteria in context
        if "materials" in step_name.lower():
            materials = context.get("materials", [])
            if not materials:
                completed = False
                details = "No materials provided"
        
        elif "dc" in step_name.lower() or "check" in step_name.lower():
            dc_value = context.get("dc")
            roll_result = context.get("roll")
            if dc_value and roll_result:
                completed = roll_result >= dc_value
                details = f"DC {dc_value}: Rolled {roll_result} - {'Success' if completed else 'Failed'}"
        
        return {
            "step_id": step["id"],
            "name": step_name,
            "description": step_desc,
            "required": step.get("required", True),
            "completed": completed,
            "details": details,
            "sources": [{"source": "checklist_executor", "step": step["id"]}]
        }


class ComputeDCExecutor:
    """
    Computes Difficulty Class (DC) values for TTRPG checks
    
    Handles various DC calculation methods and modifiers
    """
    
    def __init__(self):
        # Base DC values by difficulty
        self.base_dcs = {
            "trivial": 5,
            "easy": 10, 
            "medium": 15,
            "hard": 20,
            "very_hard": 25,
            "extreme": 30
        }
    
    def compute_dc(self, task_description: str, context: Dict[str, Any]) -> ExecutorResult:
        """
        Compute appropriate DC for a task
        
        Args:
            task_description: Description of task requiring DC
            context: Context including level, circumstances, etc.
            
        Returns:
            ExecutorResult with computed DC and modifiers
        """
        
        import time
        start_time = time.time()
        
        logger.info(f"Computing DC for: {task_description[:50]}...")
        
        try:
            errors = []
            warnings = []
            sources = []
            
            # Extract difficulty indicators from description
            difficulty = self._assess_difficulty(task_description)
            base_dc = self.base_dcs.get(difficulty, 15)
            
            # Apply modifiers from context
            modifiers = self._calculate_modifiers(task_description, context)
            
            # Compute final DC
            final_dc = base_dc + sum(mod["value"] for mod in modifiers)
            final_dc = max(5, min(final_dc, 40))  # Clamp to reasonable range
            
            result = {
                "task": task_description,
                "difficulty_assessment": difficulty,
                "base_dc": base_dc,
                "modifiers": modifiers,
                "final_dc": final_dc,
                "explanation": self._generate_dc_explanation(difficulty, base_dc, modifiers, final_dc)
            }
            
            # Add source citation
            sources.append({
                "source": "DC computation rules",
                "page": "GM Guide",
                "section": "Setting DCs"
            })
            
            return ExecutorResult(
                success=True,
                result=result,
                errors=errors,
                warnings=warnings,
                sources=sources,
                execution_time_s=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Error computing DC: {e}")
            return ExecutorResult(
                success=False,
                result=None,
                errors=[str(e)],
                warnings=[],
                sources=[],
                execution_time_s=time.time() - start_time
            )
    
    def _assess_difficulty(self, description: str) -> str:
        """Assess task difficulty from description"""
        
        desc_lower = description.lower()
        
        # Look for explicit difficulty keywords
        if any(word in desc_lower for word in ["trivial", "simple", "basic"]):
            return "trivial"
        elif any(word in desc_lower for word in ["easy", "straightforward"]):
            return "easy"
        elif any(word in desc_lower for word in ["hard", "difficult", "challenging"]):
            return "hard"
        elif any(word in desc_lower for word in ["extreme", "impossible", "legendary"]):
            return "extreme"
        elif any(word in desc_lower for word in ["very hard", "very difficult"]):
            return "very_hard"
        else:
            return "medium"  # Default
    
    def _calculate_modifiers(self, description: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate DC modifiers based on context"""
        
        modifiers = []
        
        # Level-based adjustments
        level = context.get("level")
        if level:
            if level < 5:
                modifiers.append({"name": "Low Level", "value": -2, "reason": "Character level < 5"})
            elif level > 15:
                modifiers.append({"name": "High Level", "value": +3, "reason": "Character level > 15"})
        
        # Circumstance modifiers
        circumstances = context.get("circumstances", [])
        for circumstance in circumstances:
            if "advantage" in circumstance.lower():
                modifiers.append({"name": "Advantageous", "value": -2, "reason": circumstance})
            elif "disadvantage" in circumstance.lower():
                modifiers.append({"name": "Disadvantageous", "value": +3, "reason": circumstance})
        
        # Environmental modifiers
        environment = context.get("environment", "").lower()
        if "combat" in environment:
            modifiers.append({"name": "Combat", "value": +2, "reason": "Performed in combat"})
        elif "rushed" in environment or "hurry" in environment:
            modifiers.append({"name": "Rushed", "value": +3, "reason": "Time pressure"})
        
        return modifiers
    
    def _generate_dc_explanation(self, difficulty: str, base_dc: int, modifiers: List[Dict], final_dc: int) -> str:
        """Generate explanation of DC calculation"""
        
        explanation = f"Base DC {base_dc} ({difficulty})"
        
        if modifiers:
            mod_parts = []
            for mod in modifiers:
                sign = "+" if mod["value"] >= 0 else ""
                mod_parts.append(f"{sign}{mod['value']} {mod['name']}")
            explanation += f" {' '.join(mod_parts)}"
        
        explanation += f" = DC {final_dc}"
        return explanation


class RulesVerifier:
    """
    Verifies that proposed actions comply with cited rules
    
    Prevents rule violations and ensures citation accuracy
    """
    
    def __init__(self, graph_store=None):
        self.graph_store = graph_store
    
    def verify_against_rules(self, action: str, cited_rules: List[str], 
                           context: Dict[str, Any]) -> ExecutorResult:
        """
        Verify action against cited rules
        
        Args:
            action: Proposed action or procedure
            cited_rules: List of rule IDs or references
            context: Additional context for verification
            
        Returns:
            ExecutorResult with verification status and violations
        """
        
        import time
        start_time = time.time()
        
        logger.info(f"Verifying action against {len(cited_rules)} rules")
        
        try:
            errors = []
            warnings = []
            violations = []
            sources = []
            
            # Load rules from graph or context
            rules_data = self._load_rules(cited_rules, context)
            
            if not rules_data:
                errors.append("No rules found for verification")
                return ExecutorResult(
                    success=False,
                    result=None,
                    errors=errors,
                    warnings=warnings,
                    sources=sources,
                    execution_time_s=time.time() - start_time
                )
            
            # Verify action against each rule
            for rule in rules_data:
                violation = self._check_rule_compliance(action, rule, context)
                if violation:
                    violations.append(violation)
                
                # Add rule as source
                sources.append({
                    "source": rule.get("source", "Unknown"),
                    "page": rule.get("page"),
                    "rule_id": rule.get("id"),
                    "rule_text": rule.get("text", "")[:100]  # Truncate for summary
                })
            
            # Determine success
            critical_violations = [v for v in violations if v.get("severity") == "critical"]
            success = len(critical_violations) == 0
            
            if critical_violations:
                errors.extend([v["description"] for v in critical_violations])
            
            # Add warnings for non-critical violations
            non_critical = [v for v in violations if v.get("severity") != "critical"]
            warnings.extend([v["description"] for v in non_critical])
            
            result = {
                "action": action,
                "rules_checked": len(rules_data),
                "violations": violations,
                "critical_violations": len(critical_violations),
                "compliance": "passed" if success else "failed"
            }
            
            return ExecutorResult(
                success=success,
                result=result,
                errors=errors,
                warnings=warnings,
                sources=sources,
                execution_time_s=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Error in rules verification: {e}")
            return ExecutorResult(
                success=False,
                result=None,
                errors=[str(e)],
                warnings=[],
                sources=[],
                execution_time_s=time.time() - start_time
            )
    
    def _load_rules(self, cited_rules: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Load rule data from graph or context"""
        
        rules_data = []
        
        # Try to load from graph first
        if self.graph_store:
            for rule_id in cited_rules:
                rule_node = self.graph_store.get_node(rule_id)
                if rule_node:
                    rules_data.append({
                        "id": rule_id,
                        "text": rule_node.get("properties", {}).get("text", ""),
                        "rule_type": rule_node.get("properties", {}).get("rule_type", "general"),
                        "source": "graph_store"
                    })
        
        # Fallback to context or mock data
        if not rules_data:
            for rule_id in cited_rules:
                # Mock rule data for development
                rules_data.append({
                    "id": rule_id,
                    "text": f"Mock rule text for {rule_id}",
                    "rule_type": "general",
                    "source": "mock_data",
                    "page": 100
                })
        
        return rules_data
    
    def _check_rule_compliance(self, action: str, rule: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if action complies with a specific rule"""
        
        rule_text = rule.get("text", "").lower()
        action_lower = action.lower()
        
        # Look for prohibition patterns
        if any(pattern in rule_text for pattern in ["cannot", "may not", "forbidden", "prohibited"]):
            # Extract what is prohibited
            prohibited_match = re.search(r"(?:cannot|may not|forbidden|prohibited)\s+([^.]+)", rule_text)
            if prohibited_match:
                prohibited_action = prohibited_match.group(1)
                
                # Check if action matches prohibition
                if any(word in action_lower for word in prohibited_action.split()):
                    return {
                        "rule_id": rule["id"],
                        "severity": "critical",
                        "description": f"Action '{action}' violates rule: {rule_text[:100]}",
                        "prohibited_element": prohibited_action
                    }
        
        # Look for requirement patterns
        if any(pattern in rule_text for pattern in ["must", "required", "shall"]):
            requirement_match = re.search(r"(?:must|required|shall)\s+([^.]+)", rule_text)
            if requirement_match:
                required_element = requirement_match.group(1)
                
                # Check if action meets requirement
                if not any(word in action_lower for word in required_element.split()[:3]):  # Check first 3 words
                    return {
                        "rule_id": rule["id"],
                        "severity": "warning",
                        "description": f"Action may not meet requirement: {required_element}",
                        "required_element": required_element
                    }
        
        # No violations found
        return None


class ProcedureExecutor:
    """
    Orchestrates execution of complete TTRPG procedures
    
    Combines checklist execution, DC computation, and rules verification
    """
    
    def __init__(self, graph_store=None):
        self.graph_store = graph_store
        self.checklist_executor = ChecklistExecutor(graph_store)
        self.dc_executor = ComputeDCExecutor()
        self.rules_verifier = RulesVerifier(graph_store)
    
    def execute_procedure(self, procedure_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute complete TTRPG procedure with all verification
        
        Args:
            procedure_id: Procedure to execute
            parameters: Input parameters and context
            
        Returns:
            Complete execution result with artifacts
        """
        
        import time
        start_time = time.time()
        
        logger.info(f"Executing procedure: {procedure_id}")
        
        execution_log = []
        artifacts = []
        all_sources = []
        
        try:
            # Step 1: Execute checklist
            checklist_result = self.checklist_executor.execute_checklist(procedure_id, parameters)
            execution_log.append({"step": "checklist", "result": checklist_result})
            all_sources.extend(checklist_result.sources)
            
            # Step 2: Compute any required DCs
            if "dc_required" in parameters:
                dc_result = self.dc_executor.compute_dc(parameters["dc_task"], parameters)
                execution_log.append({"step": "dc_computation", "result": dc_result})
                all_sources.extend(dc_result.sources)
                
                # Update parameters with computed DC
                if dc_result.success:
                    parameters["computed_dc"] = dc_result.result["final_dc"]
            
            # Step 3: Rules verification
            cited_rules = parameters.get("cited_rules", [])
            if cited_rules:
                verification_result = self.rules_verifier.verify_against_rules(
                    f"Execute procedure {procedure_id}",
                    cited_rules,
                    parameters
                )
                execution_log.append({"step": "verification", "result": verification_result})
                all_sources.extend(verification_result.sources)
            
            # Step 4: Generate final artifacts
            if checklist_result.success:
                artifacts.append({
                    "type": "procedure_result",
                    "procedure_id": procedure_id,
                    "checklist": checklist_result.result,
                    "parameters": parameters
                })
            
            # Determine overall success
            overall_success = checklist_result.success
            if cited_rules:
                overall_success = overall_success and verification_result.success
            
            return {
                "procedure_id": procedure_id,
                "success": overall_success,
                "execution_log": execution_log,
                "artifacts": artifacts,
                "sources": all_sources,
                "duration_s": time.time() - start_time,
                "parameters": parameters
            }
            
        except Exception as e:
            logger.error(f"Error executing procedure {procedure_id}: {e}")
            return {
                "procedure_id": procedure_id,
                "success": False,
                "error": str(e),
                "execution_log": execution_log,
                "duration_s": time.time() - start_time
            }