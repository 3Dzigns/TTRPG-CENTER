# Comprehensive Workflow Guide
## Correct MCP & Claude-Flow Usage Patterns

This guide provides three essential workflows for development, debugging, and testing with proper MCP tool coordination and Claude-Flow integration.

---

## 🎯 Quick Reference: MCP vs Claude Code

### Claude Code Task Tool (PRIMARY EXECUTION)
- Spawn agents that do actual work
- File operations (Read, Write, Edit, MultiEdit)
- Code generation and implementation
- Bash commands and system operations
- TodoWrite and task management

### MCP Tools (COORDINATION ONLY)
- **Claude-Flow**: `swarm_init`, `agent_spawn`, `task_orchestrate` - High-level coordination
- **Sequential-Thinking**: Complex analysis, multi-step reasoning
- **Code-Index**: Semantic search for large codebases (>10K LOC)
- **Playwright**: Browser automation and frontend testing
- **Context7**: Library documentation lookup
- **Memory**: Cross-session context persistence

### Claude-Flow Hooks (COORDINATION PROTOCOL)
```bash
# Before work
npx claude-flow@alpha hooks pre-task --description "[task]"
npx claude-flow@alpha hooks session-restore --session-id "swarm-[id]"

# During work
npx claude-flow@alpha hooks post-edit --file "[file]" --memory-key "swarm/[agent]/[step]"
npx claude-flow@alpha hooks notify --message "[what was done]"

# After work
npx claude-flow@alpha hooks post-task --task-id "[task]"
npx claude-flow@alpha hooks session-end --export-metrics true
```

---

## Workflow 1: From Prompt to Execution

### Overview
Transform a feature request, prompt, or requirements document into working, tested code using SPARC methodology with proper agent coordination.

### Phase 1: Initial Requirements Analysis

**Step 1.1: Setup Coordination (Optional for Complex Features)**
```javascript
// Single message - MCP coordination setup
[Coordination Setup]:
  mcp__claude-flow__swarm_init({
    topology: "hierarchical",  // hierarchical, mesh, ring, or star
    maxAgents: 8,
    strategy: "balanced"
  })

  mcp__claude-flow__agent_spawn({ type: "researcher" })
  mcp__claude-flow__agent_spawn({ type: "specification" })
  mcp__claude-flow__agent_spawn({ type: "architecture" })
```

**Step 1.2: Requirements Gathering with Parallel Agent Execution**
```javascript
// Single message - ALL agents spawned together via Claude Code's Task tool
[Parallel Agent Execution]:
  Task(
    "Requirements Researcher",
    `Analyze the prompt/requirements document:
    - Extract functional requirements
    - Identify technical constraints
    - List dependencies and integrations
    - Store findings in memory with key 'requirements/functional'
    - Run hooks: npx claude-flow@alpha hooks pre-task --description "requirements-analysis"
    - After completion: npx claude-flow@alpha hooks post-task --task-id "req-analysis"`,
    "researcher"
  )

  Task(
    "Domain Expert",
    `Research domain patterns and best practices:
    - Check Context7 MCP for relevant library docs
    - Identify industry standards
    - Document architectural patterns
    - Store in memory with key 'requirements/patterns'`,
    "researcher"
  )

  // Batch ALL todos in ONE call (5-10+ minimum)
  TodoWrite({
    todos: [
      {content: "Analyze functional requirements", status: "in_progress", activeForm: "Analyzing functional requirements"},
      {content: "Research domain patterns", status: "in_progress", activeForm: "Researching domain patterns"},
      {content: "Document technical constraints", status: "pending", activeForm: "Documenting technical constraints"},
      {content: "Create architecture design", status: "pending", activeForm: "Creating architecture design"},
      {content: "Write specifications", status: "pending", activeForm: "Writing specifications"},
      {content: "Implement core features", status: "pending", activeForm: "Implementing core features"},
      {content: "Write comprehensive tests", status: "pending", activeForm: "Writing comprehensive tests"},
      {content: "Review and validate code", status: "pending", activeForm: "Reviewing and validating code"},
      {content: "Generate documentation", status: "pending", activeForm: "Generating documentation"},
      {content: "Run final quality checks", status: "pending", activeForm: "Running final quality checks"}
    ]
  })
```

**Using Context7 MCP for Library Documentation:**
```javascript
// When you need official library docs
mcp__context7__resolve-library-id({ libraryName: "react" })
// Then use the returned ID:
mcp__context7__get-library-docs({
  context7CompatibleLibraryID: "/facebook/react",
  topic: "hooks",
  tokens: 5000
})
```

**Using Sequential-Thinking MCP for Complex Analysis:**
```javascript
// For multi-step reasoning and hypothesis testing
mcp__sequential-thinking__sequentialthinking({
  thought: "Breaking down the authentication requirement into components",
  thoughtNumber: 1,
  totalThoughts: 5,
  nextThoughtNeeded: true
})
```

### Phase 2: SPARC Planning

**Step 2.1: Specification & Pseudocode Phase**
```bash
# Use SPARC commands for systematic analysis
npx claude-flow sparc run spec-pseudocode "Build user authentication system with JWT"
```

**OR use parallel agents:**
```javascript
// Single message - Specification agents
[Parallel SPARC Phase]:
  Task(
    "Specification Agent",
    `Create detailed specification:
    - Use SPARC specification methodology
    - Define all interfaces and contracts
    - Specify data models and flows
    - Document success criteria
    - Store spec in docs/specifications/
    - Run: npx claude-flow@alpha hooks pre-task --description "specification"`,
    "specification"
  )

  Task(
    "Pseudocode Agent",
    `Design algorithms and logic:
    - Break down complex operations
    - Define step-by-step procedures
    - Identify edge cases
    - Document time/space complexity
    - Store in docs/pseudocode/`,
    "pseudocode"
  )

  // Parallel file operations
  Bash("mkdir -p docs/{specifications,pseudocode,architecture}")
```

**Step 2.2: Architecture Design**
```javascript
// Single message - Architecture phase
[Architecture Design]:
  Task(
    "System Architect",
    `Design system architecture:
    - Component diagram and relationships
    - Data flow and state management
    - API contracts and interfaces
    - Database schema design
    - Security and performance considerations
    - Store in docs/architecture/
    - Use hooks: npx claude-flow@alpha hooks post-edit --file "docs/architecture/system-design.md"`,
    "system-architect"
  )

  Task(
    "Database Architect",
    `Design data layer:
    - Entity relationships
    - Indexing strategy
    - Migration plan
    - Query optimization
    - Store schema in docs/architecture/database/`,
    "code-analyzer"
  )
```

### Phase 3: Parallel Implementation

**Step 3.1: Setup Project Structure**
```javascript
// Single message - ALL directory and config setup
[Project Setup]:
  Bash("mkdir -p src/{api,components,services,models,utils,config}")
  Bash("mkdir -p tests/{unit,integration,e2e}")
  Bash("mkdir -p docs/{api,guides}")

  Write("src/config/index.ts")  // Config files
  Write("tests/setup.ts")        // Test setup
  Write(".env.example")          // Environment template
```

**Step 3.2: Test-Driven Development with SPARC**
```bash
# Use SPARC TDD workflow
npx claude-flow sparc tdd "User authentication with JWT"
```

**OR use parallel TDD agents:**
```javascript
// Single message - TDD implementation with COORDINATION
[TDD Implementation]:
  // Optional: Setup coordination for complex features
  mcp__claude-flow__task_orchestrate({
    task: "Implement authentication system with TDD",
    strategy: "adaptive",
    priority: "high",
    maxAgents: 6
  })

  Task(
    "Test Engineer",
    `Write comprehensive tests FIRST:
    - Unit tests for each component
    - Integration tests for API
    - E2E tests for flows
    - Place in tests/unit/, tests/integration/, tests/e2e/
    - 90%+ coverage requirement
    - Run: npx claude-flow@alpha hooks pre-task --description "test-creation"
    - Store test plan in memory: 'tdd/test-plan'`,
    "tester"
  )

  Task(
    "Backend Developer",
    `Implement backend to pass tests:
    - Read test specifications from memory: 'tdd/test-plan'
    - Implement API endpoints in src/api/
    - Implement services in src/services/
    - Implement models in src/models/
    - Run tests after each component
    - Coordinate: npx claude-flow@alpha hooks post-edit --file "src/api/auth.ts"`,
    "backend-dev"
  )

  Task(
    "Frontend Developer",
    `Implement UI components:
    - React components in src/components/
    - State management in src/services/
    - API integration
    - Coordinate with backend via memory
    - Run: npx claude-flow@alpha hooks notify --message "frontend-component-complete"`,
    "coder"
  )

  Task(
    "Security Reviewer",
    `Review security continuously:
    - Check for vulnerabilities
    - Validate input sanitization
    - Review authentication flow
    - Document findings in docs/security/
    - Use: npx claude-flow@alpha hooks post-task --task-id "security-review"`,
    "reviewer"
  )

  // Update todos
  TodoWrite({
    todos: [
      {content: "Write unit tests for auth service", status: "in_progress", activeForm: "Writing unit tests for auth service"},
      {content: "Write integration tests for auth API", status: "in_progress", activeForm: "Writing integration tests for auth API"},
      {content: "Implement auth service", status: "in_progress", activeForm: "Implementing auth service"},
      {content: "Implement auth API endpoints", status: "in_progress", activeForm: "Implementing auth API endpoints"},
      {content: "Create login UI component", status: "pending", activeForm: "Creating login UI component"},
      {content: "Security review of auth flow", status: "pending", activeForm: "Reviewing security of auth flow"},
      {content: "Run all tests and verify coverage", status: "pending", activeForm: "Running all tests and verifying coverage"},
      {content: "Generate API documentation", status: "pending", activeForm: "Generating API documentation"}
    ]
  })

  // Parallel file creation for tests
  Write("tests/unit/auth.service.test.ts")
  Write("tests/integration/auth.api.test.ts")
  Write("tests/e2e/login.flow.test.ts")
```

**Step 3.3: Implementation with Memory Coordination**
```javascript
// Agents use memory for coordination
// Agent 1 stores: mcp__memory__create_entities
mcp__memory__create_entities({
  entities: [{
    name: "AuthAPI",
    entityType: "interface",
    observations: [
      "Endpoint: POST /api/auth/login",
      "Returns: JWT token and user data",
      "Requires: email and password"
    ]
  }]
})

// Agent 2 reads and implements based on memory
mcp__memory__search_nodes({ query: "AuthAPI interface" })
```

### Phase 4: Validation & Completion

**Step 4.1: Quality Gates**
```javascript
// Single message - Validation and review
[Quality Validation]:
  Task(
    "Code Reviewer",
    `Review implementation:
    - Code quality and style
    - Test coverage verification
    - Documentation completeness
    - Performance considerations
    - Store review in docs/reviews/
    - Run: npx claude-flow@alpha hooks pre-task --description "code-review"`,
    "reviewer"
  )

  Task(
    "Production Validator",
    `Validate production readiness:
    - All tests passing
    - No console errors
    - Security scan clean
    - Performance benchmarks met
    - Documentation complete
    - Run: npx claude-flow@alpha hooks session-end --export-metrics true`,
    "production-validator"
  )

  // Run all validation in parallel
  Bash("npm run lint")
  Bash("npm run typecheck")
  Bash("npm run test -- --coverage")
  Bash("npm run build")
```

**Step 4.2: Documentation Generation**
```javascript
// Single message - Documentation
[Documentation]:
  Task(
    "API Documenter",
    `Generate API documentation:
    - OpenAPI/Swagger specs
    - Usage examples
    - Integration guides
    - Place in docs/api/`,
    "api-docs"
  )

  Write("docs/api/authentication.md")
  Write("docs/guides/getting-started.md")
```

**Step 4.3: Session Completion**
```bash
# Export metrics and close session
npx claude-flow@alpha hooks session-end --export-metrics true
```

---

## Workflow 2: Debugging (Backend & Frontend)

### Overview
Systematically diagnose and fix issues across the stack using root cause analysis and proper tool selection.

### Phase 1: Problem Discovery & Analysis

**Step 1.1: Initial Investigation with Sequential Thinking**
```javascript
// Use Sequential-Thinking MCP for complex debugging
[Debug Analysis]:
  mcp__sequential-thinking__sequentialthinking({
    thought: "User reports 500 error on login endpoint. Need to trace request flow from frontend to database.",
    thoughtNumber: 1,
    totalThoughts: 8,
    nextThoughtNeeded: true
  })

  mcp__sequential-thinking__sequentialthinking({
    thought: "Hypothesis: Authentication middleware may be throwing unhandled exception. Need to check middleware chain and error handling.",
    thoughtNumber: 2,
    totalThoughts: 8,
    nextThoughtNeeded: true,
    isRevision: false
  })
```

**Step 1.2: Parallel Investigation with Agents**
```javascript
// Single message - Multi-layer investigation
[Debug Investigation]:
  // Optional: Coordinate investigation
  mcp__claude-flow__swarm_init({
    topology: "mesh",  // Peer-to-peer for collaborative debugging
    maxAgents: 5
  })

  Task(
    "Backend Investigator",
    `Investigate backend error:
    - Read error logs and stack traces
    - Check API endpoint implementation
    - Verify middleware chain
    - Test authentication flow
    - Store findings in memory: 'debug/backend-findings'
    - Run: npx claude-flow@alpha hooks pre-task --description "backend-debug"`,
    "code-analyzer"
  )

  Task(
    "Frontend Investigator",
    `Investigate frontend flow:
    - Check network requests in DevTools
    - Verify request payload format
    - Test error handling
    - Check state management
    - Store findings in memory: 'debug/frontend-findings'`,
    "coder"
  )

  Task(
    "Database Analyst",
    `Investigate data layer:
    - Check database connections
    - Verify query execution
    - Review transaction logs
    - Check schema integrity
    - Store findings in memory: 'debug/database-findings'`,
    "code-analyzer"
  )

  // Batch all file reads
  Read("src/api/auth/login.ts")
  Read("src/middleware/authenticate.ts")
  Read("src/services/auth.service.ts")
  Read("src/components/LoginForm.tsx")
  Read("tests/integration/auth.test.ts")

  // Setup todos for tracking
  TodoWrite({
    todos: [
      {content: "Analyze backend error logs", status: "in_progress", activeForm: "Analyzing backend error logs"},
      {content: "Investigate frontend request flow", status: "in_progress", activeForm: "Investigating frontend request flow"},
      {content: "Check database connectivity", status: "in_progress", activeForm: "Checking database connectivity"},
      {content: "Identify root cause", status: "pending", activeForm: "Identifying root cause"},
      {content: "Implement fix", status: "pending", activeForm: "Implementing fix"},
      {content: "Add error handling", status: "pending", activeForm: "Adding error handling"},
      {content: "Write regression tests", status: "pending", activeForm: "Writing regression tests"},
      {content: "Verify fix in all layers", status: "pending", activeForm: "Verifying fix in all layers"}
    ]
  })
```

**Step 1.3: Using Code-Index MCP for Large Codebase Navigation**
```javascript
// For codebases >10K LOC, use code-index MCP for semantic search
mcp__code-index__search({
  query: "authentication middleware error handling",
  limit: 10
})

// Navigate to specific symbols
mcp__code-index__navigate({
  symbol: "AuthenticationMiddleware",
  type: "class"
})
```

**Step 1.4: Using Playwright MCP for Frontend Debugging**
```javascript
// For frontend issues, use Playwright MCP
mcp__playwright__browser_navigate({ url: "http://localhost:3000/login" })

// Take screenshot to see current state
mcp__playwright__browser_take_screenshot({
  filename: "tests/debug-screenshots/login-error.png"
})

// Check console errors
mcp__playwright__browser_console_messages({ onlyErrors: true })

// Test form interaction
mcp__playwright__browser_click({
  element: "Login button",
  ref: "button[type='submit']"
})
```

### Phase 2: Root Cause Identification

**Step 2.1: Systematic Analysis with Memory Tracking**
```javascript
// Single message - Consolidate findings
[Root Cause Analysis]:
  Task(
    "Root Cause Analyst",
    `Analyze all investigation findings:
    - Read from memory: 'debug/backend-findings', 'debug/frontend-findings', 'debug/database-findings'
    - Identify common patterns
    - Determine root cause
    - Prioritize fixes
    - Document in docs/debugging/root-cause-analysis.md
    - Run: npx claude-flow@alpha hooks notify --message "root-cause-identified"`,
    "root-cause-analyst"
  )

  // Store consolidated findings in memory
  mcp__memory__create_entities({
    entities: [{
      name: "LoginBug",
      entityType: "bug",
      observations: [
        "Root cause: Unhandled promise rejection in auth middleware",
        "Impact: 500 error on all login attempts",
        "Fix required: Add try-catch and proper error response",
        "Prevention: Add integration tests for error cases"
      ]
    }]
  })
```

**Step 2.2: Hypothesis Testing with Sequential Thinking**
```javascript
// Continue sequential analysis
mcp__sequential-thinking__sequentialthinking({
  thought: "Hypothesis confirmed: Auth middleware throws unhandled exception when JWT validation fails. Need to wrap in try-catch and return 401 with proper error message.",
  thoughtNumber: 5,
  totalThoughts: 8,
  nextThoughtNeeded: true
})
```

### Phase 3: Fix Implementation

**Step 3.1: Parallel Fix Across Layers**
```javascript
// Single message - Multi-layer fix
[Fix Implementation]:
  Task(
    "Backend Fixer",
    `Fix backend issues:
    - Add try-catch to auth middleware
    - Implement proper error handling
    - Add error logging
    - Update error responses
    - Run: npx claude-flow@alpha hooks post-edit --file "src/middleware/authenticate.ts"`,
    "backend-dev"
  )

  Task(
    "Frontend Fixer",
    `Fix frontend issues:
    - Add error boundary
    - Improve error messages
    - Add loading states
    - Handle edge cases
    - Run: npx claude-flow@alpha hooks post-edit --file "src/components/LoginForm.tsx"`,
    "coder"
  )

  Task(
    "Test Engineer",
    `Write regression tests:
    - Test error scenarios
    - Test edge cases
    - Verify error messages
    - Place in tests/integration/
    - Run: npx claude-flow@alpha hooks pre-task --description "regression-tests"`,
    "tester"
  )

  // Batch all edits
  Edit("src/middleware/authenticate.ts", old_string, new_string)
  Edit("src/components/LoginForm.tsx", old_string, new_string)
  Write("tests/integration/auth-error-handling.test.ts")
```

**Step 3.2: Verification**
```javascript
// Single message - Comprehensive testing
[Verification]:
  Bash("npm run test -- tests/integration/auth-error-handling.test.ts")
  Bash("npm run lint")
  Bash("npm run typecheck")

  // Use Playwright for E2E verification
  mcp__playwright__browser_navigate({ url: "http://localhost:3000/login" })
  mcp__playwright__browser_fill({
    element: "email input",
    ref: "input[name='email']",
    text: "invalid@example.com"
  })
  mcp__playwright__browser_click({
    element: "submit button",
    ref: "button[type='submit']"
  })
  // Verify error message appears correctly
```

### Phase 4: Documentation & Prevention

**Step 4.1: Document Fix and Prevention Strategy**
```javascript
// Single message - Documentation
[Fix Documentation]:
  Task(
    "Documenter",
    `Document the fix:
    - Root cause explanation
    - Solution implemented
    - Tests added
    - Prevention strategies
    - Store in docs/debugging/login-500-fix.md
    - Run: npx claude-flow@alpha hooks post-task --task-id "debug-session"`,
    "api-docs"
  )

  Write("docs/debugging/login-500-fix.md")

  // Update memory with lessons learned
  mcp__memory__add_observations({
    observations: [{
      entityName: "LoginBug",
      contents: [
        "Fixed: Added try-catch to authenticate middleware",
        "Tests added: Error handling integration tests",
        "Prevention: All middleware must have error boundaries"
      ]
    }]
  })
```

**Step 4.2: Close Debug Session**
```bash
# Export debug metrics
npx claude-flow@alpha hooks session-end --export-metrics true
```

---

## Workflow 3: Clean Testing

### Overview
Implement comprehensive testing with TDD methodology, proper organization, and quality gates.

### Phase 1: Test Planning with SPARC

**Step 1.1: Use SPARC TDD Command**
```bash
# Complete TDD workflow for a feature
npx claude-flow sparc tdd "Payment processing system"

# Or run specific phases
npx claude-flow sparc run spec-pseudocode "Payment processing tests"
npx claude-flow sparc run architect "Test architecture"
```

**Step 1.2: Test Strategy with Parallel Agents**
```javascript
// Single message - Test planning
[Test Strategy]:
  mcp__claude-flow__swarm_init({
    topology: "hierarchical",
    maxAgents: 6
  })

  Task(
    "Test Strategist",
    `Create comprehensive test strategy:
    - Identify all test scenarios
    - Define test boundaries (unit, integration, e2e)
    - Specify coverage requirements (90%+)
    - Plan test data and fixtures
    - Document in docs/testing/strategy.md
    - Run: npx claude-flow@alpha hooks pre-task --description "test-strategy"`,
    "planner"
  )

  Task(
    "Test Architect",
    `Design test architecture:
    - Test organization structure
    - Shared utilities and helpers
    - Mock/stub strategies
    - Test database setup
    - CI/CD integration
    - Document in docs/testing/architecture.md`,
    "system-architect"
  )

  // Setup test directory structure
  Bash("mkdir -p tests/{unit,integration,e2e,fixtures,helpers,mocks}")
  Bash("mkdir -p tests/__snapshots__")

  TodoWrite({
    todos: [
      {content: "Define test strategy", status: "in_progress", activeForm: "Defining test strategy"},
      {content: "Design test architecture", status: "in_progress", activeForm: "Designing test architecture"},
      {content: "Write unit tests", status: "pending", activeForm: "Writing unit tests"},
      {content: "Write integration tests", status: "pending", activeForm: "Writing integration tests"},
      {content: "Write E2E tests", status: "pending", activeForm: "Writing E2E tests"},
      {content: "Setup test fixtures", status: "pending", activeForm: "Setting up test fixtures"},
      {content: "Configure CI/CD", status: "pending", activeForm: "Configuring CI/CD"},
      {content: "Verify coverage thresholds", status: "pending", activeForm: "Verifying coverage thresholds"}
    ]
  })
```

### Phase 2: Test Implementation (TDD)

**Step 2.1: Red Phase - Write Failing Tests First**
```javascript
// Single message - Write ALL tests first (TDD red phase)
[Red Phase - Write Tests]:
  Task(
    "Unit Test Engineer",
    `Write unit tests for all components:
    - Test each function/method in isolation
    - Use mocks for dependencies
    - Cover edge cases and errors
    - Place in tests/unit/
    - Tests MUST fail initially (no implementation yet)
    - Run: npx claude-flow@alpha hooks pre-task --description "unit-tests"`,
    "tester"
  )

  Task(
    "Integration Test Engineer",
    `Write integration tests:
    - Test component interactions
    - Test API endpoints with real dependencies
    - Test database operations
    - Place in tests/integration/
    - Run: npx claude-flow@alpha hooks notify --message "integration-tests-ready"`,
    "tester"
  )

  Task(
    "E2E Test Engineer",
    `Write end-to-end tests with Playwright:
    - Test complete user flows
    - Test critical paths
    - Visual regression tests
    - Place in tests/e2e/
    - Use Playwright MCP for browser automation`,
    "tester"
  )

  // Batch create all test files
  Write("tests/unit/payment.service.test.ts")
  Write("tests/unit/payment.controller.test.ts")
  Write("tests/unit/payment.validator.test.ts")
  Write("tests/integration/payment.api.test.ts")
  Write("tests/integration/payment.database.test.ts")
  Write("tests/e2e/payment.flow.test.ts")
  Write("tests/helpers/payment.fixtures.ts")
  Write("tests/setup.ts")
```

**Example Test File Structure (Unit Test):**
```typescript
// tests/unit/payment.service.test.ts
describe('PaymentService', () => {
  describe('processPayment', () => {
    it('should process valid payment successfully', async () => {
      // Arrange
      const mockPaymentGateway = createMockGateway();
      const service = new PaymentService(mockPaymentGateway);
      const payment = createValidPayment();

      // Act
      const result = await service.processPayment(payment);

      // Assert
      expect(result.status).toBe('success');
      expect(mockPaymentGateway.charge).toHaveBeenCalledWith(payment.amount);
    });

    it('should handle payment gateway errors', async () => {
      // Test error handling
    });

    it('should validate payment amount', async () => {
      // Test validation
    });
  });
});
```

**Step 2.2: Run Tests to Verify They Fail**
```javascript
// Single message - Verify red phase
[Verify Red Phase]:
  Bash("npm run test -- --testPathPattern=tests/unit")
  Bash("npm run test -- --testPathPattern=tests/integration")

  // Document that tests are failing as expected
  mcp__memory__create_entities({
    entities: [{
      name: "PaymentTDD",
      entityType: "tdd-session",
      observations: [
        "Red phase complete: All tests written and failing",
        "Unit tests: 12 failing",
        "Integration tests: 5 failing",
        "Ready for green phase implementation"
      ]
    }]
  })
```

**Step 2.3: Green Phase - Implement to Pass Tests**
```javascript
// Single message - Parallel implementation
[Green Phase - Implementation]:
  mcp__claude-flow__task_orchestrate({
    task: "Implement payment system to pass all tests",
    strategy: "adaptive",
    priority: "high"
  })

  Task(
    "Backend Developer",
    `Implement payment system:
    - Read test specifications from tests/unit/ and tests/integration/
    - Implement PaymentService in src/services/
    - Implement PaymentController in src/api/
    - Implement validators in src/validators/
    - Run tests after each component
    - Run: npx claude-flow@alpha hooks post-edit --file "src/services/payment.service.ts"`,
    "backend-dev"
  )

  Task(
    "Test Runner",
    `Continuously run tests:
    - Watch mode for unit tests
    - Report failing tests
    - Track progress to green
    - Store results in memory`,
    "tester"
  )

  // Batch implementation files
  Write("src/services/payment.service.ts")
  Write("src/api/payment.controller.ts")
  Write("src/validators/payment.validator.ts")
  Write("src/models/payment.model.ts")
```

**Step 2.4: Refactor Phase - Clean Up**
```javascript
// Single message - Code review and refactoring
[Refactor Phase]:
  Task(
    "Code Reviewer",
    `Review and suggest improvements:
    - Check for code duplication
    - Verify design patterns
    - Suggest performance optimizations
    - Ensure SOLID principles
    - Document in docs/reviews/`,
    "reviewer"
  )

  Task(
    "Refactoring Specialist",
    `Refactor while keeping tests green:
    - Extract reusable functions
    - Improve naming and structure
    - Add JSDoc comments
    - Optimize algorithms
    - Run tests after each refactor`,
    "refactoring-expert"
  )

  // Verify tests still pass
  Bash("npm run test")
  Bash("npm run lint -- --fix")
```

### Phase 3: E2E Testing with Playwright

**Step 3.1: Browser-Based Testing**
```javascript
// Single message - E2E test implementation
[E2E Testing]:
  Task(
    "E2E Test Engineer",
    `Implement E2E tests with Playwright MCP:
    - Test payment flow end-to-end
    - Test error scenarios
    - Visual regression testing
    - Performance testing
    - Place in tests/e2e/`,
    "tester"
  )

  // Use Playwright MCP for test implementation
  Write("tests/e2e/payment-happy-path.test.ts")
  Write("tests/e2e/payment-error-handling.test.ts")
```

**Example E2E Test with Playwright MCP:**
```typescript
// tests/e2e/payment-happy-path.test.ts
test('complete payment flow', async () => {
  // Navigate to payment page
  await mcp__playwright__browser_navigate({
    url: 'http://localhost:3000/payment'
  });

  // Fill payment form
  await mcp__playwright__browser_fill({
    element: 'card number input',
    ref: 'input[name="cardNumber"]',
    text: '4242424242424242'
  });

  // Submit payment
  await mcp__playwright__browser_click({
    element: 'submit button',
    ref: 'button[type="submit"]'
  });

  // Verify success message
  await mcp__playwright__browser_snapshot();

  // Take screenshot for visual regression
  await mcp__playwright__browser_take_screenshot({
    filename: 'tests/e2e/screenshots/payment-success.png'
  });
});
```

### Phase 4: Coverage & Quality Gates

**Step 4.1: Coverage Analysis**
```javascript
// Single message - Coverage verification
[Coverage Analysis]:
  Task(
    "Coverage Analyst",
    `Analyze test coverage:
    - Run coverage report
    - Identify untested code
    - Generate coverage badges
    - Document gaps
    - Store report in docs/testing/coverage/`,
    "code-analyzer"
  )

  // Run coverage with thresholds
  Bash("npm run test -- --coverage --coverageThreshold='{\"global\":{\"branches\":90,\"functions\":90,\"lines\":90,\"statements\":90}}'")

  // Check coverage report
  Read("coverage/coverage-summary.json")
```

**Step 4.2: Production Validation**
```javascript
// Single message - Final validation
[Production Validation]:
  Task(
    "Production Validator",
    `Validate production readiness:
    - All tests passing (unit, integration, E2E)
    - Coverage meets threshold (90%+)
    - No lint errors
    - Type checking passes
    - Performance benchmarks met
    - Security scan clean
    - Run: npx claude-flow@alpha hooks pre-task --description "production-validation"`,
    "production-validator"
  )

  // Run all quality gates in parallel
  Bash("npm run test")
  Bash("npm run lint")
  Bash("npm run typecheck")
  Bash("npm run build")

  // Security check (if configured)
  Bash("npm audit")

  TodoWrite({
    todos: [
      {content: "All unit tests passing", status: "completed", activeForm: "All unit tests passing"},
      {content: "All integration tests passing", status: "completed", activeForm: "All integration tests passing"},
      {content: "All E2E tests passing", status: "completed", activeForm: "All E2E tests passing"},
      {content: "Coverage above 90%", status: "completed", activeForm: "Coverage above 90%"},
      {content: "No lint errors", status: "completed", activeForm: "No lint errors"},
      {content: "Type checking passes", status: "completed", activeForm: "Type checking passes"},
      {content: "Build successful", status: "completed", activeForm: "Build successful"},
      {content: "Security scan clean", status: "completed", activeForm: "Security scan clean"}
    ]
  })
```

**Step 4.3: CI/CD Integration**
```javascript
// Single message - CI/CD setup
[CI/CD Configuration]:
  Task(
    "CI/CD Engineer",
    `Setup automated testing pipeline:
    - Configure test runners
    - Setup coverage reporting
    - Configure quality gates
    - Setup deployment triggers
    - Document in docs/cicd/
    - Run: npx claude-flow@alpha hooks post-edit --file ".github/workflows/test.yml"`,
    "cicd-engineer"
  )

  Write(".github/workflows/test.yml")
  Write(".github/workflows/coverage.yml")
```

**Example CI/CD Configuration:**
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run test -- --coverage
      - run: npm run test:e2e
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json
```

### Phase 5: Test Maintenance

**Step 5.1: Test Documentation**
```javascript
// Single message - Test documentation
[Test Documentation]:
  Write("docs/testing/README.md")  // Test overview and running instructions
  Write("docs/testing/writing-tests.md")  // Test writing guidelines
  Write("docs/testing/fixtures.md")  // Test data and fixtures guide
  Write("docs/testing/mocking.md")  // Mocking strategies
```

**Step 5.2: Session Completion**
```bash
# Export test metrics
npx claude-flow@alpha hooks session-end --export-metrics true
```

---

## 📋 Best Practices Summary

### 1. Always Batch Operations
```javascript
// ✅ CORRECT: Single message with all operations
[Single Message]:
  Task("Agent 1", "...", "type1")
  Task("Agent 2", "...", "type2")
  Task("Agent 3", "...", "type3")
  TodoWrite({ todos: [...10 todos...] })
  Read("file1.ts")
  Read("file2.ts")
  Write("file3.ts")

// ❌ WRONG: Multiple messages
Message 1: Task("Agent 1")
Message 2: Task("Agent 2")
Message 3: TodoWrite
```

### 2. Use MCP Tools Correctly
```javascript
// ✅ CORRECT: MCP for coordination, Task tool for execution
mcp__claude-flow__swarm_init({ topology: "mesh" })  // Coordination
Task("Agent", "Do work...", "coder")  // Actual execution

// ❌ WRONG: Using only MCP without Task tool
mcp__claude-flow__agent_spawn({ type: "coder" })  // No actual execution
```

### 3. File Organization
```javascript
// ✅ CORRECT: Organized in subdirectories
Write("tests/unit/feature.test.ts")
Write("docs/api/endpoints.md")
Write("src/services/feature.service.ts")

// ❌ WRONG: Files in root
Write("feature.test.ts")  // Never in root!
Write("API_DOCS.md")  // Never in root!
```

### 4. Use Hooks for Coordination
```bash
# Always use hooks in Task instructions
npx claude-flow@alpha hooks pre-task --description "task-name"
npx claude-flow@alpha hooks post-edit --file "path/to/file"
npx claude-flow@alpha hooks post-task --task-id "task-id"
npx claude-flow@alpha hooks session-end --export-metrics true
```

### 5. Memory for Cross-Agent Coordination
```javascript
// Agent 1: Store findings
mcp__memory__create_entities({
  entities: [{
    name: "FeatureSpec",
    entityType: "specification",
    observations: ["API endpoint: POST /api/feature", "Returns: JSON"]
  }]
})

// Agent 2: Read and use
mcp__memory__search_nodes({ query: "FeatureSpec" })
```

### 6. TodoWrite with 5-10+ Items
```javascript
// ✅ CORRECT: Comprehensive todo list
TodoWrite({
  todos: [
    {content: "Task 1", status: "in_progress", activeForm: "Doing Task 1"},
    {content: "Task 2", status: "in_progress", activeForm: "Doing Task 2"},
    {content: "Task 3", status: "pending", activeForm: "Doing Task 3"},
    {content: "Task 4", status: "pending", activeForm: "Doing Task 4"},
    {content: "Task 5", status: "pending", activeForm: "Doing Task 5"},
    {content: "Task 6", status: "pending", activeForm: "Doing Task 6"},
    {content: "Task 7", status: "pending", activeForm: "Doing Task 7"},
    {content: "Task 8", status: "pending", activeForm: "Doing Task 8"}
  ]
})

// ❌ WRONG: Single or few todos
TodoWrite({ todos: [{content: "Task 1", status: "pending", activeForm: "Doing Task 1"}] })
```

---

## 🔧 Tool Selection Matrix

| Scenario | Primary Tool | Alternative |
|----------|-------------|-------------|
| Complex analysis | Sequential-Thinking MCP | Native reasoning |
| Large codebase navigation | Code-Index MCP | Grep tool |
| Library documentation | Context7 MCP | Web search |
| Frontend debugging | Playwright MCP | Browser DevTools |
| Backend debugging | Code-Analyzer agent | Manual debugging |
| Agent coordination | Claude-Flow MCP | Manual coordination |
| Cross-session memory | Memory MCP | File-based storage |
| Test execution | Bash (npm test) | Manual testing |
| Code review | Reviewer agent | Manual review |
| Architecture design | System-Architect agent | Manual design |

---

## 📚 Additional Resources

- **SPARC Commands**: `npx claude-flow sparc modes`
- **Agent List**: See CLAUDE.md for all 54 agents
- **MCP Servers**: `claude mcp list`
- **Hooks Reference**: `npx claude-flow@alpha hooks --help`
- **Project Documentation**: See `/docs` directory

---

**Remember**:
- 🎯 **MCP coordinates, Task tool executes**
- ⚡ **Batch everything in single messages**
- 📁 **Never save to root, use subdirectories**
- 🔗 **Use hooks for agent coordination**
- 💾 **Use memory for cross-agent communication**
- ✅ **Write 5-10+ todos in one TodoWrite call**
