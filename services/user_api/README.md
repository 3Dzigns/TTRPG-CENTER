# User API Service

## Purpose
User-facing API for /ask, /plan, /run endpoints and session memory management.

## Responsibilities
- **Query Processing**: Handle user queries through /ask endpoint
- **Planning**: Generate execution plans through /plan endpoint
- **Execution**: Run planned workflows through /run endpoint
- **Session Memory**: Maintain user session context and history
- **User Experience**: Optimize response times and interaction quality

## Architecture
- FastAPI service running on configurable ports (dev: 8002, test: 8183, prod: 8284)
- Integration with orchestrator service for query processing
- Session-based context management
- Real-time response streaming

## Setup
```bash
# Install dependencies
pip install -e .[dev]

# Run service
python -m services.user_api.api

# Run tests
pytest tests/unit/user_api/
pytest tests/functional/user_api/
```

## Environment Configuration
- `env/{ENV}/config/user_api.env` - Service-specific configuration
- `env/{ENV}/data/sessions/` - Session data storage
- `env/{ENV}/logs/user_api/` - Service logs

## Core Components

### Query Handler (`/ask`)
- Process natural language queries
- Route to orchestrator for classification and retrieval
- Format responses for user consumption
- Handle streaming responses for long-running queries

### Plan Generator (`/plan`)
- Generate execution plans for complex queries
- Break down multi-step workflows
- Estimate execution time and resources
- Provide plan validation and optimization

### Workflow Executor (`/run`)
- Execute validated plans
- Coordinate with multiple services
- Provide real-time progress updates
- Handle error recovery and rollback

### Session Manager
- Maintain conversation context
- Track user preferences and history
- Implement session timeout and cleanup
- Provide session analytics and insights

## API Endpoints
- `POST /ask` - Process user query and return answer
- `POST /plan` - Generate execution plan for complex request
- `POST /run` - Execute a validated plan
- `GET /sessions/{session_id}` - Get session information
- `DELETE /sessions/{session_id}` - Clear session data
- `GET /sessions/{session_id}/history` - Get conversation history
- `GET /healthz` - Health check endpoint

## Integration Points
- **Orchestrator Service**: Query classification and retrieval
- **Admin API**: System status and configuration
- **Ingest Service**: Direct upload and processing requests
- **User UI**: Frontend interface (Phase 5)

## Performance Requirements
- Response time: <2s for simple queries, <30s for complex plans
- Concurrent users: Support 100+ simultaneous sessions
- Session persistence: Maintain context across requests
- Streaming: Real-time response streaming for long operations

## Status
🚧 **In Development** - Part of MVP v2 microservices architecture migration