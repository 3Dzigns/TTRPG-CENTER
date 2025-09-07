# TTRPG Center — Architecture Flowchart

This document provides a high-level flowchart of the project showing entry points, core services, auth/security, and data stores. The Mermaid diagram can be rendered in VS Code (Mermaid extension) or any Mermaid-compatible viewer.

```mermaid
%% Include mirrors docs/ARCH_FLOW.mmd
graph TD
  subgraph Clients
    C1[Browser - User UI]
    C2[Browser - Admin UI]
    C3[Browser - Feedback UI]
    C4[Browser - Requirements UI]
    C5[API Clients]
  end
  subgraph Applications
    AUser[app_user.py\nUser UI FastAPI app]
    AAdmin[app_admin.py\nAdmin UI FastAPI app]
    AFeedback[app_feedback.py\nFeedback FastAPI app]
    AReq[app_requirements.py\nRequirements FastAPI app]
    ACore[src_common/app.py: app\nCore API FastAPI app]
  end
  subgraph Core_Services[Core Services]
    RAG[/orchestrator.service\nroutes: /rag/*/]
    Classifier[orchestrator.classifier]
    Policies[orchestrator.policies]
    ModelRouter[orchestrator.router]
    Prompts[orchestrator.prompts]
    Retriever[orchestrator.retriever]
    PlanRouter[/app_plan_run.py\nroutes: /api/(plan|run|models|budget)*/]
    WorkflowRouter[/app_workflow.py\nroutes: /api/workflow/*/]
    Planner[src_common.planner.plan]
    Budget[src_common.planner.budget]
    Executor[src_common.runtime.execute]
    State[src_common.runtime.state]
    GraphStore[src_common.graph.store]
  end
  subgraph Admin_Services
    AdminStatus[src_common.admin.status]
    AdminIngest[src_common.admin.ingestion]
    AdminDict[src_common.admin.dictionary]
    AdminTest[src_common.admin.testing]
    AdminCache[src_common.admin.cache_control]
  end
  subgraph Auth_Security[Auth & Security]
    OAuthEndpoints[/src_common.oauth_endpoints\nroutes: /auth/*/]
    OAuthService[src_common.oauth_service]
    JWT[src_common.jwt_service]
    AuthDB[(src_common.auth_database\nSQLite: auth.db)]
    CORS[src_common.cors_security]
    TLS[src_common.tls_security]
  end
  subgraph Data_Stores[Data & External]
    Astra[(AstraDB - optional)]
    Artifacts[(artifacts/{env}\nlocal JSON chunks)]
    Templates[(templates/*)]
    Static[(static/*)]
  end
  C1 -->|HTTP GET/POST| AUser
  C2 -->|HTTP GET/POST| AAdmin
  C3 -->|HTTP POST| AFeedback
  C4 -->|HTTP GET/POST| AReq
  C5 -->|HTTP| ACore
  AUser -->|/api/query\n(real_rag_query)| RAG
  AUser --> Templates
  AUser --> Static
  AUser -.->|WebSocket| C1
  RAG --> Classifier --> Policies --> ModelRouter --> Prompts --> Retriever
  Retriever --> Astra
  Retriever --> Artifacts
  RAG -->|JSON answer + chunks| AUser
  ACore --> PlanRouter
  ACore --> WorkflowRouter
  PlanRouter --> Planner
  PlanRouter --> Budget
  PlanRouter --> GraphStore
  WorkflowRouter --> State
  WorkflowRouter --> Executor
  Executor --> State
  Executor -->|write| Artifacts
  AAdmin --> Templates
  AAdmin --> Static
  AAdmin --> AdminStatus
  AAdmin --> AdminIngest
  AAdmin --> AdminDict
  AAdmin --> AdminTest
  AAdmin --> AdminCache
  AdminIngest --> Artifacts
  AReq --> Templates
  AReq --> Static
  AReq --> OAuthEndpoints
  AReq --> JWT
  AReq --> AuthDB
  AFeedback --> Templates
  AFeedback --> Static
  AFeedback -->|create regression tests\n+ bug bundles| Artifacts
  AUser --> OAuthEndpoints
  AAdmin --> OAuthEndpoints
  OAuthEndpoints --> OAuthService
  OAuthEndpoints --> JWT
  JWT --> AuthDB
  OAuthService --> AuthDB
  AUser --> CORS
  AAdmin --> CORS
  AReq --> CORS
  AFeedback --> CORS
  AUser --> TLS
  AAdmin --> TLS
  AReq --> TLS
  AFeedback --> TLS
```

Notes
- src_common/app.py mounts: /rag/*, /api/workflow/*, /api/plan|run endpoints.
- app_user.py uses an internal TestClient call to /rag/ask then invokes scripts/rag_openai.py for OpenAI responses.

