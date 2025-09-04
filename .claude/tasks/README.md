# TTRPG Center - Task Management System

This directory contains the structured task management system for Claude Code when working on the TTRPG Center project.

## Directory Structure

```
.claude/tasks/
├── README.md           # This file - explains the task management system
├── active/            # Currently active tasks
├── completed/         # Archived completed tasks for reference
└── templates/         # Task templates and documentation standards
    └── task_template.md  # Standard task documentation template
```

## Task Management Workflow

### 1. Planning Phase
- Claude Code creates a detailed plan in plan mode
- Plan is documented using the task template in `templates/task_template.md`
- Task file is created in `active/` directory as `active/TASK_NAME.md`
- User reviews and approves the plan before implementation begins

### 2. Implementation Phase
- Task status is updated to "In Progress"
- Regular progress updates are added to the Progress Log section
- Technical decisions and issues are documented as they occur
- File modifications are tracked in the Technical Details section

### 3. Completion Phase
- Task is marked as "Completed"
- Completion Summary is filled out with deliverables and impact
- Handover notes are documented for future engineers
- Task file is moved from `active/` to `completed/` directory

## Task Template Sections

### Essential Information
- **Task Overview**: Objective, context, and success criteria
- **Technical Requirements**: Prerequisites, constraints, and acceptance criteria
- **Implementation Plan**: Phased approach with specific tasks

### Progress Tracking
- **Progress Log**: Regular updates with dates and accomplishments
- **Issues & Resolutions**: Documentation of blockers and solutions
- **Technical Details**: Architecture decisions and file modifications

### Knowledge Transfer
- **Completion Summary**: What was delivered and its impact
- **Handover Notes**: Critical information for future engineers
- **Lessons Learned**: What went well and areas for improvement

## Naming Conventions

### Task Files
- Use descriptive, kebab-case names: `implement-user-authentication.md`
- Include phase information when relevant: `phase1-pdf-ingestion-pipeline.md`
- Use verb-noun format: `fix-query-classification-performance.md`

### Task Identification
- Tasks should have clear, action-oriented titles
- Include the component or system being modified
- Specify the type of work: implementation, bugfix, enhancement, refactor

## Best Practices

### Documentation
- Update progress regularly, not just at completion
- Document technical decisions and their rationale
- Include code snippets or configuration examples when helpful
- Record both successes and failures for learning

### Handover Preparation
- Always assume another engineer will continue the work
- Document any assumptions made during implementation
- Highlight any technical debt or known limitations
- Provide clear next steps for related functionality

### Task Organization
- Break large tasks into smaller, manageable pieces
- Use checklists for tracking progress
- Link related tasks when dependencies exist
- Archive completed tasks promptly for reference

## Integration with CLAUDE.md

This task management system works in conjunction with the planning workflow defined in `CLAUDE.md`:

1. **Before starting work**: Create task plan using template
2. **During implementation**: Update task progress regularly  
3. **After completion**: Document results and move to completed/

The task files serve as both planning documents and historical records, ensuring continuity across different work sessions and providing valuable context for future development.

## Quick Reference

### Creating a New Task
1. Copy `templates/task_template.md` to `active/your-task-name.md`
2. Fill out the Task Overview and Technical Requirements
3. Create detailed Implementation Plan
4. Submit for user review before proceeding

### Completing a Task
1. Fill out Completion Summary with deliverables
2. Document Handover Notes for future engineers
3. Record Lessons Learned
4. Move file from `active/` to `completed/`
5. Update any related documentation

### Finding Information
- Check `active/` for current work in progress
- Search `completed/` for similar past tasks
- Reference `templates/` for documentation standards