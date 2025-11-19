# Async Ingestion Pipeline (Scaffold)

This directory contains the scaffolded implementation of the fully-asynchronous ingestion
pipeline described in `Prompt Lib/P01_Fully_Async_Ingestion_Pipeline_Plan.md`.

Current status:

- Environment configuration lives in `ingestion/config/settings.py`.
- Celery app factory defined in `ingestion/core/celery_app.py`.
- In-memory job registry placeholder in `ingestion/core/job_registry.py`.
- Worker packages in `ingestion/workers/` expose Celery tasks (stub behavior for now).
- CLI stubs live in `ingestion/cli/` (`status_monitor`, `log_monitor`, `job_management`).
- `docker/docker-compose-async.yml` bootstraps the service topology for iterative development.

Next steps include implementing persistent storage (Postgres/Cassandra/Neo4j integrations),
replacing placeholders with production logic, and adding comprehensive testing per the plan.
