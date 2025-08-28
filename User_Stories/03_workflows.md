# Graph Workflows — User Stories & Test Plan

**Scope:** Multi-step task orchestration using graph-based workflows

## User Stories

- As a **stakeholder**, I want **Graph workflow engine with node/edge execution** (**WF-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Character Creation workflow implementation** (**WF-002**, priority=high), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Intelligent routing between RAG and workflow modes** (**WF-003**, priority=high), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### WF-001: Graph workflow engine with node/edge execution
- [ ] Workflows stored as graphs with nodes and transitions
- [ ] Node metadata includes prompts and dictionary references
- [ ] Deterministic execution with state tracking
### WF-002: Character Creation workflow implementation
- [ ] Multi-step character creation flow
- [ ] System-specific validation rules
- [ ] Integration with RAG for legal options
### WF-003: Intelligent routing between RAG and workflow modes
- [ ] Query classification for routing decisions
- [ ] Fallback to OpenAI training data when appropriate
- [ ] Clear labeling of response sources

## Test Plan

### Unit Tests

- WF-001: Unit tests for core logic/config implementing 'Graph workflow engine with node/edge execution'.
- WF-002: Unit tests for core logic/config implementing 'Character Creation workflow implementation'.
- WF-003: Unit tests for core logic/config implementing 'Intelligent routing between RAG and workflow modes'.

### Functional (E2E) Tests

- WF-001: End-to-end scenario demonstrating all acceptance criteria.
- WF-002: End-to-end scenario demonstrating all acceptance criteria.
- WF-003: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- WF-001: Snapshot/behavioral checks to prevent future regressions.
- WF-002: Snapshot/behavioral checks to prevent future regressions.
- WF-003: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Router only calls allowlisted tools; no shell/exec.
- Workflow state machine prevents cycles and privilege escalation.
- Audit logs record routing decisions and justification.

## Example Snippet

```python
class Engine:
    def __init__(self, graph): self.graph = graph
    def run(self, state):
        node = self.graph.start
        visited = set()
        while node:
            if node.id in visited: raise RuntimeError("cycle detected")
            visited.add(node.id)
            state = node.execute(state)
            node = self.graph.next(node, state)
        return state
```
