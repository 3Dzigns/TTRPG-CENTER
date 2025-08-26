# Memory: Environments

All work must respect strict **Dev / Test / Prod isolation**.  
No cross-environment data or config contamination is permitted.

## Environment Configurations
- **DEV**
  - Port: 8000
  - Purpose: active development, requirement validation gates
  - Special: `/validate-dev` endpoint
- **TEST**
  - Port: 8181
  - Purpose: user acceptance testing (UAT)
  - Special: 👍 feedback → regression tests, 👎 feedback → bug bundles
- **PROD**
  - Port: 8282
  - Purpose: production use with ngrok exposure
  - Special: ngrok public URL auto-display

## Config Loading
- Use `.env.dev`, `.env.test`, `.env.prod` files.
- Secrets are **never** hardcoded; load via config loader.
- Promotion only allowed `dev → test → prod` (adjacent only).
- Rollback supported using `rollback.ps1`.

## Databases
- **AstraDB (Vector Store)**
  - Primary vector + semantic search DB
  - Ingested chunks and metadata live here
- **Astra Graph**
  - Graph workflows, entity relationships
- **Redis (Optional)**
  - For job queueing and status pub/sub
  - Never stores long-term data

## Guardrails
- No migration or promotion without a `--dry-run` plan.
- Each ENV has its own build pointer (`builds/` directory).
- Logs, bug bundles, and test artifacts must stay scoped to their ENV.

## Definition of Done
- Each environment can start independently with its own `.env.*`.
- Promoting a build updates only the target ENV pointer.
- Rollback restores the prior ENV pointer safely.
- `/status` endpoint reflects the correct environment and build ID.
