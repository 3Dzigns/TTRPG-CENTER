# WebUI Planner

## Purpose
Plan UI/UX architecture, component hierarchies, user flows, and accessibility strategies for web applications.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Planning new UI features or redesigns
- Creating wireframes and component hierarchies
- Designing user flows and interactions
- Inputs include `feature_spec`, `ui_requirements`, or `design_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `feature_spec` (string, optional) - Feature description
- `ui_requirements` (object, optional) - UI/UX requirements
- `target_framework` (string, optional) - React/Vue/Angular/etc.

## Procedure (must follow)
1) Use `sequential-thinking` to analyze requirements and break down UI planning into phases:
   - Component hierarchy
   - User flows
   - State management
   - Accessibility requirements
2) Read existing UI patterns from `memory` key `webui/patterns`.
3) If `target_framework` specified, use `context7` to retrieve framework best practices.
4) Use `code-index` to discover existing components for reuse.
5) Create planning artifacts:
   - `UIComponentTree.md` - Component hierarchy
   - `UserFlows.md` - User interaction flows
   - `AccessibilityPlan.md` - WCAG compliance checklist
   - `StateManagement.md` - State architecture
6) Store planning decisions in `memory` under `webui/plans/{feature_name}`.

## Outputs (artifacts)
- `UIComponentTree.md` - Visual component hierarchy
- `UserFlows.md` - User journey diagrams
- `AccessibilityPlan.md` - Accessibility checklist (WCAG 2.1)
- `StateManagement.md` - State architecture plan
- `ImplementationRoadmap.json` - Phased implementation plan

## Failure policy
- If **required tools** (sequential-thinking, memory) unavailable, STOP and emit remediation note.
- If optional tools unavailable, proceed with reduced functionality and note limitations.
- Never fabricate tool outputs.

## Version
1.0.0
