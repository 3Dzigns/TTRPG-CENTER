# TTRPG Center - MVP Documentation

## Overview

TTRPG Center is an AI-powered assistant for tabletop role-playing games, featuring hybrid RAG (Retrieval-Augmented Generation) capabilities and graph-based workflows for complex multi-step tasks like character creation.

## Quick Start

### Prerequisites

- Python 3.8+ installed
- PowerShell (Windows) or PowerShell Core
- Internet connection for API services
- ngrok installed (optional, for PROD environment public access)

### Environment Setup

1. **Clone/Extract** the project to your desired location
2. **Navigate** to the TTRPG_Center directory
3. **Run** the development environment:
   ```powershell
   .\scripts\run-dev.ps1
   ```

### Default URLs

- **DEV**: http://localhost:8000
- **TEST**: http://localhost:8181  
- **PROD**: http://localhost:8282 (+ ngrok tunnel if enabled)

### User Interfaces

- **Admin UI**: `/admin` - System management, ingestion, testing
- **User UI**: `/user` - Query interface for end users
- **Health Check**: `/health` - Basic system status
- **Detailed Status**: `/status` - Full system information

## Architecture

### Multi-Environment Design

The system supports three distinct environments:

1. **DEV**: Development and coding environment
2. **TEST**: User Acceptance Testing with thumbs-up/down feedback
3. **PROD**: Production environment with public ngrok exposure

### Immutable Builds

- Builds are created with timestamps: `YYYY-MM-DD_HH-mm-ss_build-####`
- Source code is hashed and stored with each build
- Environments point to specific builds via pointer files
- Rollback capability to previous builds

### Data Flow

```
PDF Input → Pass A (Parse/Chunk) → Pass B (Enrich/Normalize) → Pass C (Graph Compile) → RAG Store
                                                                                      ↓
Query → Router → RAG Lookup / Graph Workflow → Response → User Feedback → Test/Bug Creation
```

## Core Components

### 1. Ingestion Pipeline

Three-pass system for processing TTRPG source materials:

- **Pass A - Structure**: PDF parsing, chunking, primary metadata extraction
- **Pass B - Enrichment**: Dictionary normalization, secondary metadata, store writes  
- **Pass C - Graph Compilation**: Workflow graph updates for affected systems/editions

### 2. RAG System

- **Vector Store**: AstraDB with semantic search
- **Chunking**: Single-concept chunks with preserved page references
- **Metadata**: Rich metadata including book, section, system, edition
- **Normalization**: Cross-system dictionary for term standardization

### 3. Graph Workflows

- **Multi-step Tasks**: Character creation, level advancement, etc.
- **Graph Structure**: Nodes (steps) and edges (transitions) with conditions
- **Execution Engine**: Deterministic workflow execution with state tracking
- **Integration**: RAG lookups during workflow execution for canonical data

### 4. Routing Intelligence  

Query classification determines processing path:
- **RAG Lookup**: Factual queries, list requests
- **Graph Workflow**: Multi-step tasks requiring guided interaction
- **Fallback**: OpenAI training data when local store insufficient

## User Experience

### Admin Interface

- **System Status**: Environment info, health checks, build tracking
- **Ingestion Console**: File upload, processing progress, dictionary management
- **Testing**: Regression test management, bug bundle review
- **Requirements**: Immutable requirements and feature request tracking

### User Interface

- **Query Input**: Text input with performance metrics display
- **Response Area**: Multimodal response display with source attribution
- **Feedback System**: Thumbs up/down for automatic test/bug generation
- **Visual Design**: LCARS-inspired retro terminal aesthetic

## Testing & Quality

### Automatic Test Generation

- **Thumbs Up** in TEST environment automatically creates regression test cases
- **Thumbs Down** creates comprehensive bug bundles for developer review
- Test cases include query, context, expected outcomes, and validation criteria

### DEV Environment Gates

Before promotion, DEV must pass:
- All initial requirements validation
- All approved feature requests validation  
- Only superseded requirements can be ignored (with approval trail)

### Bug Bundle Contents

Negative feedback generates detailed diagnostic information:
- Complete agent execution trace
- Token usage and performance metrics
- Retrieved chunks and scoring
- System state and build information
- User feedback and suggested ground truth

## Configuration

### Environment Variables

Each environment (`.env.dev`, `.env.test`, `.env.prod`) requires:

```
# Astra Database (Vector/RAG)  
ASTRA_DB_APPLICATION_TOKEN=<your-token>
ASTRA_DB_API_ENDPOINT=<your-endpoint>
ASTRA_DB_ID=<your-db-id>
ASTRA_DB_KEYSPACE=<your-keyspace>
ASTRA_DB_REGION=<your-region>

# Astra Graph Database
ASTRA_GRAPHDB_ID=<your-graph-id>
ASTRA_GRAPHDB_TOKEN=<your-graph-token>

# OpenAI
OPENAI_API_KEY=<your-openai-key>

# Runtime
APP_ENV=dev|test|prod
PORT=8000|8181|8282  
NGROK_ENABLED=true|false
NGROK_AUTHTOKEN=<your-ngrok-token>
```

### Security Notes

- Never commit API keys or tokens to version control
- Environment files should remain local only
- Bug bundles and logs must not contain secrets
- Admin UI shows only ngrok public URLs, never auth tokens

## Operations

### Build Management

```powershell
# Create new build
.\scripts\build.ps1

# Promote build to TEST
.\scripts\promote.ps1 -BuildId "2025-08-25_14-30-15_build-1234" -Env test

# Promote to PROD  
.\scripts\promote.ps1 -BuildId "2025-08-25_14-30-15_build-1234" -Env prod

# Rollback environment
.\scripts\rollback.ps1 -Env test
```

### Running Environments

```powershell
# Development
.\scripts\run-dev.ps1

# Test environment  
.\scripts\run-test.ps1

# Production
.\scripts\run-prod.ps1
```

### Monitoring

- Health endpoint: `GET /health`
- Detailed status: `GET /status` 
- Log files in `logs/<env>/`
- Performance metrics in bug bundles
- Promotion history in `logs/<env>/promotions.jsonl`

## Requirements Management

### Immutable Requirements

- Requirements stored as versioned JSON documents
- Never edit existing requirement files in place
- Superseding requirements create new versioned documents
- Full audit trail of requirement changes

### Feature Requests

- Formal approval workflow for feature requests
- Feature requests can supersede requirements after approval
- JSON schema validation for both requirements and requests
- Integration with DEV testing gates

## Development

### Adding New Features

1. Create feature request using `feature_request.schema.json`
2. Get approval through admin interface
3. Implement feature in DEV environment
4. Ensure all tests pass (including new feature requirements)
5. Build and promote through TEST to PROD

### Extending Workflows

1. Define new workflow graph structure
2. Implement nodes with appropriate prompts and validations
3. Connect to dictionary for term normalization
4. Test through ingestion Pass C compilation
5. Validate through user interface

### Custom Integrations

The system is designed for extensibility:
- Plugin architecture for additional data sources
- Configurable workflow graphs  
- Extensible dictionary system
- Modular RAG components

## Troubleshooting

### Common Issues

**Server won't start**: Check environment variables are set correctly
**Ingestion fails**: Verify AstraDB credentials and connectivity  
**Workflows not executing**: Check graph compilation in Pass C
**Tests failing**: Review requirements vs. implementation alignment

### Debug Information

- Server logs: Console output during development
- Bug bundles: Comprehensive diagnostic data from user feedback
- Health checks: Service connectivity validation
- Build manifests: Source code and dependency tracking

## Future Roadmap

### Planned Enhancements

- Image input support for character sheets
- Party-wide memory mode  
- Advanced workflow graphs (combat, spell effects)
- Multi-user collaboration features
- Mobile-responsive interface improvements

### Integration Opportunities

- VTT (Virtual Tabletop) integration
- Character sheet import/export
- Dice rolling integration  
- Campaign management features
- Social features for gaming groups

---

For technical support or feature requests, please use the admin interface or create properly formatted feature request documents following the provided JSON schemas.