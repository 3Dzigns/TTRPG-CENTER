import logging
from typing import Dict, Any, List
from .graph_engine import WorkflowGraph, WorkflowNode, WorkflowEdge, NodeType, EdgeCondition

logger = logging.getLogger(__name__)

def create_character_creation_workflow(system: str = "Pathfinder 2E") -> WorkflowGraph:
    """Create character creation workflow for specified system"""
    
    workflow = WorkflowGraph(
        workflow_id=f"character_creation_{system.lower().replace(' ', '_')}",
        name=f"Character Creation - {system}",
        description=f"Step-by-step character creation for {system}",
        system=system,
        start_node="welcome"
    )
    
    # Node 1: Welcome and Overview
    welcome_node = WorkflowNode(
        node_id="welcome",
        node_type=NodeType.STEP,
        title="Character Creation Welcome",
        prompt=f"""Welcome to {system} character creation! I'll guide you through creating your character step by step.

We'll cover:
1. Choosing your ancestry (race)
2. Selecting a background
3. Picking your class
4. Assigning ability scores
5. Selecting starting feats
6. Choosing equipment
7. Final character details

Are you ready to begin? (Reply 'yes' to continue or 'help' for more information)""",
        expected_outputs=["user_ready"],
        metadata={"intro_step": True}
    )
    workflow.add_node(welcome_node)
    
    # Node 2: System Rules Overview
    rules_node = WorkflowNode(
        node_id="rules_overview",
        node_type=NodeType.RAG_LOOKUP,
        title="System Rules Overview",
        prompt=f"Let me provide an overview of {system} character creation rules.",
        rag_query_template=f"{system} character creation overview basic rules",
        expected_outputs=["rules_summary"],
        metadata={"provides_context": True}
    )
    workflow.add_node(rules_node)
    
    # Node 3: Choose Ancestry
    ancestry_node = WorkflowNode(
        node_id="choose_ancestry",
        node_type=NodeType.RAG_LOOKUP,
        title="Choose Ancestry",
        prompt=f"""Now let's choose your character's ancestry. In {system}, your ancestry determines:
- Ability score boosts and flaws
- Ancestry feats you can select
- Physical traits and heritage
- Starting hit points (for some ancestries)

Let me show you the available ancestries:""",
        rag_query_template=f"{system} ancestry list character creation available races",
        required_inputs=["user_ready"],
        expected_outputs=["ancestry_choice", "ancestry_bonuses"],
        validation_rules={
            "ancestry_choice": {"type": "string", "required": True}
        },
        metadata={"decision_point": True}
    )
    workflow.add_node(ancestry_node)
    
    # Node 4: Choose Background
    background_node = WorkflowNode(
        node_id="choose_background",
        node_type=NodeType.RAG_LOOKUP,
        title="Choose Background",
        prompt=f"""Great choice! Now let's select your character's background. Your background represents what your character did before becoming an adventurer.

Backgrounds provide:
- Ability score boosts
- Skill training
- Background feat
- Starting equipment

Let me show you the available backgrounds:""",
        rag_query_template=f"{system} background list character creation available",
        required_inputs=["ancestry_choice"],
        expected_outputs=["background_choice", "background_bonuses"],
        validation_rules={
            "background_choice": {"type": "string", "required": True}
        },
        metadata={"decision_point": True}
    )
    workflow.add_node(background_node)
    
    # Node 5: Choose Class
    class_node = WorkflowNode(
        node_id="choose_class",
        node_type=NodeType.RAG_LOOKUP,
        title="Choose Class",
        prompt=f"""Now for the big decision - your character's class! This determines:
- Your role in the party
- Hit points and proficiencies
- Class features and abilities
- Spell casting (if applicable)
- Available class feats

Here are the available classes:""",
        rag_query_template=f"{system} class list character creation available classes",
        required_inputs=["background_choice"],
        expected_outputs=["class_choice", "class_features"],
        validation_rules={
            "class_choice": {"type": "string", "required": True}
        },
        metadata={"decision_point": True, "major_choice": True}
    )
    workflow.add_node(class_node)
    
    # Node 6: Assign Ability Scores
    abilities_node = WorkflowNode(
        node_id="assign_abilities",
        node_type=NodeType.STEP,
        title="Assign Ability Scores",
        prompt=f"""Time to determine your character's ability scores! In {system}, you'll apply boosts from:
1. Your ancestry
2. Your background  
3. Your class
4. Four free boosts you can assign

Let me calculate your starting scores based on your choices so far, then you can assign your free boosts.

Current boosts:
- Ancestry: {{ancestry_bonuses}}
- Background: {{background_bonuses}}
- Class: {{class_features}}

You have 4 free boosts to assign. Each ability can only receive one boost per source.""",
        required_inputs=["class_choice"],
        expected_outputs=["final_abilities"],
        validation_rules={
            "final_abilities": {"type": "dict", "required": True}
        },
        metadata={"calculation_step": True}
    )
    workflow.add_node(abilities_node)
    
    # Node 7: Select Feats
    feats_node = WorkflowNode(
        node_id="select_feats",
        node_type=NodeType.RAG_LOOKUP,
        title="Select Starting Feats",
        prompt=f"""Now let's choose your starting feats! At 1st level, you typically get:
- 1 Ancestry feat
- 1 Background feat (from your background)
- 1 Class feat
- 1 Skill feat (sometimes)

Let me show you the available feats for your choices:""",
        rag_query_template=f"{system} level 1 feats {'{ancestry_choice}'} {'{class_choice}'}",
        required_inputs=["final_abilities"],
        expected_outputs=["selected_feats"],
        validation_rules={
            "selected_feats": {"type": "list", "required": True}
        },
        metadata={"decision_point": True}
    )
    workflow.add_node(feats_node)
    
    # Node 8: Starting Equipment
    equipment_node = WorkflowNode(
        node_id="starting_equipment",
        node_type=NodeType.RAG_LOOKUP,
        title="Starting Equipment",
        prompt=f"""Let's outfit your character! You'll receive:
- Equipment from your class
- Equipment from your background
- Starting gold to purchase additional gear

Here's what your class and background provide:""",
        rag_query_template=f"{system} starting equipment {'{class_choice}'} {'{background_choice}'}",
        required_inputs=["selected_feats"],
        expected_outputs=["equipment_list", "remaining_gold"],
        metadata={"equipment_step": True}
    )
    workflow.add_node(equipment_node)
    
    # Node 9: Final Details
    finalize_node = WorkflowNode(
        node_id="finalize_character",
        node_type=NodeType.COMPLETION,
        title="Finalize Character",
        prompt=f"""Excellent! Let's finalize your character. Here's what we've created:

**Ancestry:** {{ancestry_choice}}
**Background:** {{background_choice}}  
**Class:** {{class_choice}}
**Ability Scores:** {{final_abilities}}
**Feats:** {{selected_feats}}
**Equipment:** {{equipment_list}}

I'll now calculate your final statistics:
- Hit Points
- Armor Class
- Saving Throws
- Skill bonuses
- Attack bonuses

Would you like me to generate a complete character sheet, or would you like to modify anything?""",
        required_inputs=["equipment_list"],
        expected_outputs=["character_sheet"],
        metadata={"completion_step": True}
    )
    workflow.add_node(finalize_node)
    
    # Define edges (workflow flow)
    edges = [
        # Welcome -> Rules Overview
        WorkflowEdge("welcome_to_rules", "welcome", "rules_overview", 
                    EdgeCondition.SUCCESS),
        
        # Rules -> Ancestry
        WorkflowEdge("rules_to_ancestry", "rules_overview", "choose_ancestry", 
                    EdgeCondition.ALWAYS),
        
        # Ancestry -> Background
        WorkflowEdge("ancestry_to_background", "choose_ancestry", "choose_background", 
                    EdgeCondition.SUCCESS),
        
        # Background -> Class
        WorkflowEdge("background_to_class", "choose_background", "choose_class", 
                    EdgeCondition.SUCCESS),
        
        # Class -> Abilities
        WorkflowEdge("class_to_abilities", "choose_class", "assign_abilities", 
                    EdgeCondition.SUCCESS),
        
        # Abilities -> Feats
        WorkflowEdge("abilities_to_feats", "assign_abilities", "select_feats", 
                    EdgeCondition.SUCCESS),
        
        # Feats -> Equipment
        WorkflowEdge("feats_to_equipment", "select_feats", "starting_equipment", 
                    EdgeCondition.SUCCESS),
        
        # Equipment -> Finalize
        WorkflowEdge("equipment_to_finalize", "starting_equipment", "finalize_character", 
                    EdgeCondition.SUCCESS),
    ]
    
    for edge in edges:
        workflow.add_edge(edge)
    
    # Validate workflow
    issues = workflow.validate_workflow()
    if issues:
        logger.warning(f"Workflow validation issues: {issues}")
    else:
        logger.info(f"Character creation workflow for {system} created successfully")
    
    return workflow

def create_level_up_workflow(system: str = "Pathfinder 2E") -> WorkflowGraph:
    """Create level advancement workflow"""
    
    workflow = WorkflowGraph(
        workflow_id=f"level_up_{system.lower().replace(' ', '_')}",
        name=f"Level Advancement - {system}",
        description=f"Level up an existing character in {system}",
        system=system,
        start_node="level_check"
    )
    
    # Node 1: Check Current Level
    level_check_node = WorkflowNode(
        node_id="level_check",
        node_type=NodeType.INPUT,
        title="Current Level Check",
        prompt="What is your character's current level? I'll help you advance to the next level.",
        expected_outputs=["current_level", "target_level"],
        validation_rules={
            "current_level": {"type": "integer", "min": 1, "max": 19}
        }
    )
    workflow.add_node(level_check_node)
    
    # Node 2: Level Benefits
    benefits_node = WorkflowNode(
        node_id="level_benefits",
        node_type=NodeType.RAG_LOOKUP,
        title="Level Advancement Benefits",
        prompt=f"Let me look up what you gain at level {{target_level}} in {system}:",
        rag_query_template=f"{system} level {'{target_level}'} advancement benefits",
        required_inputs=["target_level"],
        expected_outputs=["level_benefits"],
        metadata={"lookup_step": True}
    )
    workflow.add_node(benefits_node)
    
    # Node 3: Apply Changes
    apply_changes_node = WorkflowNode(
        node_id="apply_changes",
        node_type=NodeType.COMPLETION,
        title="Apply Level Changes",
        prompt="""Based on your level advancement, here are the changes to apply:

**New Benefits:** {{level_benefits}}

I'll help you:
1. Increase hit points
2. Update saving throws and skills
3. Select new feats (if applicable)
4. Choose new spells (if applicable)
5. Update any class features

Let's go through each change step by step.""",
        required_inputs=["level_benefits"],
        expected_outputs=["updated_character"],
        metadata={"completion_step": True}
    )
    workflow.add_node(apply_changes_node)
    
    # Define edges
    edges = [
        WorkflowEdge("check_to_benefits", "level_check", "level_benefits", EdgeCondition.SUCCESS),
        WorkflowEdge("benefits_to_apply", "level_benefits", "apply_changes", EdgeCondition.SUCCESS)
    ]
    
    for edge in edges:
        workflow.add_edge(edge)
    
    return workflow