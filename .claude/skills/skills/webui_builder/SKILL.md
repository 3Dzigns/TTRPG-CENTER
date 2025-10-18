# WebUI Builder

## Purpose
Implement UI components, styling, event handlers, and state management for web applications.

## Required tools
- code-index (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- sequential-thinking (>=0.1.0)

## When to use
- Building new React/Vue/Angular components
- Implementing design system components
- Adding interactivity and state management
- Inputs include `component_spec`, `design_tokens`, or `build_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `component_spec` (object, required) - Component specification
- `framework` (string, optional) - React/Vue/Angular/Svelte
- `style_system` (string, optional) - CSS/Tailwind/Styled-components

## Procedure (must follow)
1) Use `code-index` to locate existing components and patterns.
2) Read build state from `memory` key `webui/build/{component_name}`.
3) For complex builds, use `sequential-thinking` to plan implementation steps.
4) Use `context7` to retrieve framework-specific documentation and patterns.
5) Implement components following existing patterns:
   - Component file structure
   - Props/state management
   - Event handlers
   - Styling approach
6) Create build artifacts:
   - Component source files
   - Unit test files
   - Storybook stories (if applicable)
   - `BuildReport.md`
7) Store build state in `memory` under `webui/build/{component_name}`.

## Outputs (artifacts)
- Component source files (JSX/TSX/Vue)
- Unit test files
- `BuildReport.md` - Implementation summary
- `ComponentAPI.md` - Props/events documentation
- Storybook stories (if applicable)

## Failure policy
- If **required tools** (code-index, memory) unavailable, STOP and emit remediation note.
- Never create components without checking existing patterns first.
- Always emit build artifacts even if incomplete.

## Version
1.0.0
