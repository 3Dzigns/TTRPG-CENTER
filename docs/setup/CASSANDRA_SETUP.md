# Cassandra Setup for TTRPG Center (DEV/CI)

This guide explains how to run the local Apache Cassandra instance that backs the vector store in development and CI environments (FR-031).

## 1. Overview
- **Container name:** `ttrpg-cassandra-dev`
- **Image:** `cassandra:5`
- **Keyspace:** `ttrpg`
- **Table:** `chunks`
- **Port:** `9042`
- **Env toggle:** `VECTOR_STORE_BACKEND=cassandra`

The application automatically provisions the keyspace/table at startup. Production continues to use AstraDB unless the feature flag is flipped.

## 2. Starting the service
```bash
# Build images (installs cassandra-driver inside the app container)
docker compose -f env/dev/docker-compose.yml build app

# Start the stack (brings up Cassandra + dependencies)
docker compose -f env/dev/docker-compose.yml up -d app

# Check Cassandra health
docker compose -f env/dev/docker-compose.yml ps cassandra-dev
```

The Cassandra service includes a health check that runs `cqlsh -e 'DESCRIBE KEYSPACES'` until the node is ready.

## 3. Verifying connectivity
```bash
# Open a CQL shell in the container
docker compose -f env/dev/docker-compose.yml exec cassandra-dev cqlsh

# List keyspaces (ttrpg should appear after first app start)
DESCRIBE KEYSPACES;

# Inspect the chunks table
USE ttrpg;
DESCRIBE TABLE chunks;
```

## 4. Environment variables
Ensure the app container sees the following (set in `docker-compose.dev.yml` and `env/dev/config/.env`):
```
VECTOR_STORE_BACKEND=cassandra
CASSANDRA_CONTACT_POINTS=cassandra-dev
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ttrpg
CASSANDRA_TABLE=chunks
CASSANDRA_CONSISTENCY=LOCAL_ONE
```
Optional authentication:
```
CASSANDRA_USERNAME=your_user
CASSANDRA_PASSWORD=your_password
```

## 5. Switching back to AstraDB
Set `VECTOR_STORE_BACKEND=astra` (and provide Astra credentials) to revert to the managed service. The rest of the ingestion pipeline uses the same abstraction, so no code changes are required.

## 6. Resetting data
```bash
# Drop all chunks in the current keyspace
docker compose -f env/dev/docker-compose.yml exec cassandra-dev cqlsh -e "TRUNCATE ttrpg.chunks;"
```

## 7. Troubleshooting
| Symptom | Fix |
|---------|-----|
| `NoHostAvailable` errors on startup | Ensure `cassandra-dev` container is healthy; rerun `docker compose up -d`. |
| Schema mismatch errors | Delete `cassandra_data_dev` volume and restart to allow auto-provisioning. |
| `RuntimeError: Vector store upsert failed` | Backend set to Astra with `ASTRA_REQUIRE_CREDS=true` but credentials missing; either provide credentials or switch to Cassandra. |
| Tests hang waiting for Cassandra | Verify health check finished (`docker compose ... ps cassandra-dev`). |

## 8. CI considerations
- GitHub Actions can reuse the same service definition:
  ```yaml
  services:
    cassandra:
      image: cassandra:5
      ports:
        - 9042:9042
      options: >-
        --health-cmd "cqlsh -e 'DESCRIBE KEYSPACES'"
        --health-interval 20s --health-timeout 10s --health-retries 10
  ```
- Export `VECTOR_STORE_BACKEND=cassandra` in the job environment.
- Run migrations or smoke-tests with `pytest -q` inside the app container.

## 9. Reference
- `src_common/vector_store/cassandra.py` – Cassandra adapter implementation.
- `docker-compose.dev.yml` – service definition and env wiring.
- `docs/features/FR-031-*` – functional requirement details.