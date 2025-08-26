# TTRPG Center - API Testing Guide

## Testing the Complete Implementation

### Prerequisites
```powershell
# Start the development server
.\scripts\run-dev.ps1
```

## 1. Health & Status Tests

### Basic Health Check
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "ok": true,
  "env": "dev",
  "timestamp": 1692974400.123
}
```

### Detailed System Status
```bash
curl http://localhost:8000/status
```

**Expected Response:**
```json
{
  "env": "dev",
  "port": 8000,
  "build_id": "dev",
  "health_checks": {
    "astra_vector": "connected",
    "astra_graph": "connected",
    "openai": "connected"
  },
  "performance": {
    "total_queries": 0,
    "queries_last_hour": 0,
    "avg_latency_ms": 0,
    "success_rate": 0.0,
    "active_sessions": 0
  },
  "workflows": 2,
  "active_executions": 0
}
```

## 2. Query Processing Tests

### Test 1: RAG Lookup Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is armor class in D&D?",
    "session_id": "test_session_001",
    "user_id": "test_user",
    "context": {"system": "D&D 5E"}
  }'
```

**Expected Response Structure:**
```json
{
  "query_id": "abc12345",
  "query": "What is armor class in D&D?", 
  "response": "Armor Class (AC) represents how difficult...",
  "query_type": "rag_lookup",
  "routing_confidence": 0.85,
  "latency_ms": 750,
  "model": "openai:gpt-4o-mini",
  "tokens": {"prompt": 150, "completion": 75, "total": 225},
  "sources": [
    {
      "source_id": "dnd5e_phb_2014",
      "page": 144,
      "score": 0.92,
      "text_preview": "Your Armor Class (AC) represents..."
    }
  ],
  "success": true,
  "session_id": "test_session_001"
}
```

### Test 2: Workflow Initiation Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Help me create a character in Pathfinder 2E",
    "session_id": "test_session_002",
    "context": {"system": "Pathfinder 2E"}
  }'
```

**Expected Response Structure:**
```json
{
  "query_id": "def67890",
  "query": "Help me create a character in Pathfinder 2E",
  "response": "Welcome to Pathfinder 2E character creation!...",
  "query_type": "workflow",
  "workflow_execution_id": "exec_abc123",
  "workflow_status": "active", 
  "routing_confidence": 0.92,
  "success": true
}
```

### Test 3: Calculation Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Roll 2d6+3 for damage",
    "session_id": "test_session_003"
  }'
```

**Expected Response:**
```json
{
  "query_type": "calculation",
  "response": "Calculation queries not yet implemented. Please rephrase as a lookup query.",
  "success": true
}
```

## 3. Feedback System Tests

### Test Positive Feedback (👍)
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "abc12345",
    "type": "positive",
    "query": "What is armor class in D&D?",
    "response": "Armor Class (AC) represents how difficult it is to hit you in combat...",
    "context": {
      "app_env": "test",
      "query_type": "rag_lookup",
      "model_used": "openai:gpt-4o-mini",
      "sources": []
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "test_case_id": "REG-1692974400-abc12345",
  "file_path": "tests/regression/cases/REG-1692974400-abc12345.json",
  "expectations_detected": 3,
  "message": "Thank you! I've created a test case to ensure consistent quality for similar questions."
}
```

**Verify**: Check that a new file was created in `tests/regression/cases/`

### Test Negative Feedback (👎)
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "def67890",
    "type": "negative", 
    "query": "What is armor class in Pathfinder?",
    "response": "In D&D, armor class represents...",
    "user_feedback": "Wrong system - this is D&D info but I asked about Pathfinder",
    "context": {
      "app_env": "test",
      "query_type": "rag_lookup"
    },
    "execution_trace": []
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "bug_id": "bugid_20250825-143045-def67890",
  "severity": "high",
  "message": "Thank you for the feedback! I've created a detailed report for the development team to review."
}
```

**Verify**: Check that a new file was created in `bugs/`

## 4. Workflow API Tests

### Start New Workflow
```bash
curl -X POST http://localhost:8000/api/workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "character_creation_pathfinder_2e",
    "context": {"system": "Pathfinder 2E"}
  }'
```

**Expected Response:**
```json
{
  "execution_id": "exec_abc123",
  "workflow_id": "character_creation_pathfinder_2e", 
  "current_node": "welcome",
  "status": "started"
}
```

### Continue Workflow
```bash
curl -X POST http://localhost:8000/api/workflow/continue \
  -H "Content-Type: application/json" \
  -d '{
    "execution_id": "exec_abc123",
    "user_input": "yes"
  }'
```

**Expected Response:**
```json
{
  "execution_id": "exec_abc123",
  "response": "Great! Let's start by choosing your ancestry...",
  "current_node": "choose_ancestry", 
  "status": "active",
  "step_result": {
    "success": true,
    "node_type": "step"
  }
}
```

## 5. Web Interface Testing

### Admin Interface Test
1. Navigate to http://localhost:8000/admin
2. Verify all cards load:
   - System Status (shows health checks)
   - Ingestion Console (placeholder)
   - Dictionary Management (placeholder)
   - Regression Tests (placeholder)
   - Bug Bundles (placeholder)
   - Requirements (placeholder)

### User Interface Test  
1. Navigate to http://localhost:8000/user
2. Submit query: "What is a longsword?"
3. Verify:
   - Response appears with real content (not placeholder)
   - Timer shows actual processing time
   - Token count appears
   - Model name appears
   - 👍/👎 buttons work and show thank you messages

## 6. Performance Testing

### Query Timing Test
```bash
# Time a simple query
time curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are hit points?", "session_id": "perf_test"}'
```

**Expected**: Response in under 2 seconds for simple queries.

### Load Testing (Basic)
```bash
# Send 10 concurrent queries
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/query \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Test query $i\", \"session_id\": \"load_test_$i\"}" &
done
wait
```

Check system status afterward to see performance metrics.

## 7. Error Handling Tests

### Invalid Query Test
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "", "session_id": "error_test"}'
```

**Expected**: `400 Bad Request` with error message.

### Invalid JSON Test  
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test" invalid json}'
```

**Expected**: `400 Bad Request` with "invalid json" error.

### Non-existent Endpoint Test
```bash
curl http://localhost:8000/api/nonexistent
```

**Expected**: `404 Not Found` with appropriate error message.

## 8. Data Verification Tests

### Check Generated Files

**Regression Test Files:**
```bash
ls -la tests/regression/cases/
ls -la tests/regression/snapshots/
```

**Bug Bundle Files:**
```bash
ls -la bugs/
```

**Dictionary File:**
```bash
python -c "from app.ingestion.dictionary import get_dictionary; print(get_dictionary().get_stats())"
```

**Metrics Export:**
```bash  
python -c "from app.common.metrics import get_metrics_collector; print(get_metrics_collector().export_metrics())"
```

## 9. Integration Test Scenarios

### Complete User Journey Test
1. User visits `/user` interface
2. Submits query: "How do I create a fighter in D&D 5E?"
3. System routes to workflow
4. User continues through character creation steps
5. User gives 👍 feedback
6. Admin reviews generated regression test

### Cross-System Query Test
1. Query: "What's the difference between D&D and Pathfinder armor class?"
2. Verify response addresses both systems appropriately
3. Check source citations include both D&D and Pathfinder sources

### Fallback System Test
1. Query: "What's the best pizza topping for game night?"
2. Verify system uses fallback response
3. Check response includes disclaimer about general knowledge

## Expected Performance Baselines

- **Health Check**: < 50ms
- **Simple RAG Query**: 500-1500ms  
- **Complex Workflow Query**: 800-2000ms
- **Feedback Processing**: < 200ms
- **Status Endpoint**: < 100ms

## Troubleshooting

### If Health Checks Fail
1. Check environment variables in `.env.dev`
2. Verify internet connectivity for AstraDB/OpenAI
3. Check console logs for initialization errors

### If Queries Return Errors
1. Check that vector store initialized successfully
2. Verify OpenAI API key is valid
3. Look for detailed error messages in console logs

### If No Files Generated
1. Check write permissions on test/bug directories  
2. Verify feedback API endpoints work in isolation
3. Check console logs for file writing errors

---

**This testing guide covers all major functionality of your TTRPG Center implementation. All tests should pass with the fully integrated system.**