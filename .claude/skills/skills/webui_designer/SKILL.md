# WebUI Designer

## Purpose
Design design systems, component libraries, responsive patterns, theming systems, and UI architecture.

## Required tools
- context7 (>=0.1.0)
- sequential-thinking (>=0.1.0)

## Optional tools
- memory (>=0.3.0)
- code-index (>=0.1.0)

## When to use
- Creating design systems or component libraries
- Designing responsive layouts and breakpoint strategies
- Theming and brand implementation
- UI architecture planning
- Inputs include `design_system_spec`, `brand_guidelines`, or `architecture_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `design_system_spec` (object, optional) - Design system requirements
- `brand_guidelines` (object, optional) - Brand colors/fonts/spacing
- `framework` (string, optional) - Target framework

## Procedure (must follow)
1) Use `sequential-thinking` to plan design system architecture:
   - Design tokens structure
   - Component taxonomy
   - Theming strategy
   - Responsive breakpoints
2) Use `context7` to retrieve design system best practices (Material/Ant/Chakra patterns).
3) Read existing design decisions from `memory` key `webui/design/system`.
4) Use `code-index` to analyze existing component patterns.
5) Create design artifacts:
   - `DesignTokens.json` - Colors/typography/spacing
   - `ComponentLibrary.md` - Component taxonomy
   - `ThemingStrategy.md` - Theme architecture
   - `ResponsivePatterns.md` - Breakpoint strategy
   - `DesignSystemGuidelines.md` - Usage guidelines
6) Store design decisions in `memory` under `webui/design/system`.

## Outputs (artifacts)
- `DesignTokens.json` - Design token definitions
- `ComponentLibrary.md` - Component catalog
- `ThemingStrategy.md` - Theme architecture
- `ResponsivePatterns.md` - Responsive guidelines
- `DesignSystemGuidelines.md` - Implementation guide
- Figma/Sketch integration plan

## Failure policy
- If `context7` unavailable, proceed with generic design patterns and note limitation.
- Always create design tokens even for simple projects.
- Never skip responsive patterns.

## Version
1.0.0
