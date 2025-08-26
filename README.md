# TTRPG Center - MVP Prototype

AI-powered TTRPG assistant with RAG and Graph Workflows for character creation, rules lookup, and multi-step game tasks.

## 🚀 Quick Start

```powershell
# Run development environment
.\scripts\run-dev.ps1

# Access interfaces
# Admin: http://localhost:8000/admin  
# User:  http://localhost:8000/user
# Health: http://localhost:8000/health
```

## 📋 Requirements Checklist

- [x] Multi-environment setup (DEV/TEST/PROD)
- [x] Immutable build system with promotion workflow  
- [x] PowerShell automation scripts
- [x] Backend server with health endpoints
- [x] Admin UI framework (System Status, Ingestion, Dictionary, Tests, Bugs)
- [x] User UI framework (Query panel, Response area, Feedback system)
- [x] JSON schemas for requirements and feature requests
- [x] Example regression tests and bug bundles
- [x] Configuration templates with secure secrets handling
- [ ] AstraDB RAG integration (skeleton ready)
- [ ] Graph workflow engine implementation  
- [ ] Three-pass ingestion pipeline
- [ ] Dictionary normalization system
- [ ] UAT feedback → automatic test/bug generation

## 🏗️ Architecture

```
DEV (8000) → TEST (8181) → PROD (8282 + ngrok)
     ↓            ↓             ↓
Build System → Promotion → Rollback Capable
     ↓
Multi-Pass Ingestion → RAG Store → Graph Workflows
```

## 📁 Project Structure

```
TTRPG_Center/
├── app/                    # Backend, UI, ingestion, workflows
├── config/                 # Environment configs (.env.*)
├── scripts/                # PowerShell automation  
├── builds/                 # Immutable build artifacts
├── tests/regression/       # Auto-generated test cases
├── bugs/                   # Thumbs-down feedback bundles
├── docs/requirements/      # Immutable requirements + schemas
└── assets/background/      # UI assets
```

## 🔧 Environment Setup  

1. **Copy** `.env` files are pre-configured with provided API keys
2. **Install** Python 3.8+ and PowerShell
3. **Optional**: Install ngrok for PROD public access
4. **Run**: `.\scripts\run-dev.ps1`

## 🎯 Core Features

### Admin Interface (`/admin`)
- System status with health checks
- Ingestion console (placeholder)
- Dictionary management (placeholder)  
- Regression test management
- Bug bundle review
- Requirements tracking

### User Interface (`/user`)
- LCARS-inspired retro terminal design
- Query input with performance metrics
- Response area with thumbs up/down feedback
- Timer, token counter, model identification

### Build Management
```powershell
.\scripts\build.ps1                                          # Create build
.\scripts\promote.ps1 -BuildId <id> -Env test               # Promote  
.\scripts\rollback.ps1 -Env test                           # Rollback
```

## 🧪 Testing Strategy

- **👍 in TEST** → Auto-creates regression test case
- **👎 in TEST/PROD** → Creates comprehensive bug bundle  
- **DEV Gates** → Must pass all requirements + approved features
- **Immutable Requirements** → JSON schema validated

## 📊 Example Outputs

### Bug Bundle (from 👎 feedback)
```json
{
  "bug_id": "bugid_20250825-104223",
  "query": "How much does a longsword cost?",
  "user_feedback": "Wrong system pricing",
  "agent_trace": [...],
  "token_usage": {"total": 1185},
  "ground_truth_hint": "System contamination issue"
}
```

### Regression Test (from 👍 feedback)  
```json
{
  "query": "List level 1 feats in PF2E",
  "expected": {
    "contains": ["Ancestry Feats", "Class Feats"],
    "forbidden": ["Epic Feats"]
  }
}
```

## 🔐 Security

- API keys stored in local `.env` files only
- Never commit secrets to version control
- Admin UI shows public URLs only (no tokens)
- Bug bundles sanitized of sensitive data

## 📚 Documentation  

- Full documentation: `docs/documentation.md`
- Requirements: `docs/requirements/2025-08-25_MVP_Requirements.json`
- Schemas: `docs/requirements/*.schema.json`

## 🚧 Implementation Status

**✅ Complete:**
- Multi-environment framework
- Build/promotion system  
- Admin/User UI skeletons
- Requirements management
- Testing infrastructure

**🔄 Next Steps:**
- AstraDB RAG integration
- Graph workflow engine
- Ingestion pipeline implementation
- Dictionary system
- Feedback → test/bug automation

---

**Ready for Development Team Handoff** 🎉